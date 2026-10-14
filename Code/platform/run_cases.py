#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_cases: 无人机识别与定位系统 14 用例批量测试(无头, 不依赖界面)
=================================================================
复用平台的真实检测链路(DroneDetector: YOLOv8 + 先验约束 + AKF +
SEARCH/LOCKED/COAST 状态机), 逐个用例跑检测并逐帧落盘 CSV,
最后汇总成 summary.csv / summary.md(论文实验章直接引用)。

14 个用例:
  C01-C05  不同输入源(仿真/真实录像, 含长录像中后段偏移)基线, 默认参数
  C06-C08  置信度门限扫描(0.20/0.35/0.50), 同一仿真录像
  C09-C10  等效尺寸敏感性(0.230/0.310), 同一仿真录像
  C11-C13  TCP 实时链路重复性(3 轮 × 20s)
  C14      真实摄像头(无摄像头自动跳过并记原因, --camera 强制跑)

用法:
  python run_cases.py                     # 跑全部(离线900帧/用例, TCP 20s)
  python run_cases.py --only 1-10         # 只跑指定用例(支持逗号/区间)
  python run_cases.py --frames 300        # 离线用例每例最多300帧
  python run_cases.py --tcp-seconds 10    # TCP 用例每轮秒数
  python run_cases.py --camera            # 启用 C14 摄像头
  python run_cases.py --tcp 127.0.0.1:14590
"""
import argparse
import csv
import os
import socket
import sys
import time
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import cv2
import numpy as np

from platform_detector import DroneDetector
from tcp_frame_source import TcpFrameSource

OUT_DIR = os.path.join(BASE, "test_runs")

CSV_HEADER = [
    "frame", "ts_ms", "status", "det", "tracked", "conf",
    "x1", "y1", "x2", "y2", "box_w", "box_h",
    "z_raw", "z_akf", "z_pred1s", "azim_deg", "elev_deg", "fps", "src",
]

# 用例表: min_lock=锁定率合格线(None=仅统计不判定, 用于内容未知的素材)
CASES = [
    dict(cid=1,  name="仿真闭环录像基线",     kind="file", target="sim_demo_simft.mp4",
         conf=0.20, size=0.270, min_lock=0.80,
         note="闭环仿真主录像, 目标持续在视野"),
    dict(cid=2,  name="仿真录像(早期标定版)", kind="file", target="sim_recorded.mp4",
         conf=0.20, size=0.270, min_lock=0.80,
         note="0.230 标定时期录像, 含远距离死区段"),
    dict(cid=3,  name="长录像中后段稳定性(30s偏移)", kind="file",
         target="sim_demo_simft.mp4", start=900,
         conf=0.20, size=0.270, min_lock=0.80,
         note="4.6GB 长录像跳至第900帧, 验证中后段重新捕获稳定性"),
    dict(cid=4,  name="真实场景录像1",        kind="file", target="demo_recorded.mp4",
         conf=0.20, size=0.270, min_lock=None,
         note="真实无人机外场录像, 仅统计不设合格线"),
    dict(cid=5,  name="真实场景录像2",        kind="file", target="demo_video.mp4",
         conf=0.20, size=0.270, min_lock=None,
         note="真实无人机外场录像, 仅统计不设合格线"),
    dict(cid=6,  name="门限扫描 conf=0.20",   kind="file", target="sim_demo_simft.mp4",
         conf=0.20, size=0.270, min_lock=None, note="敏感性实验不设合格线(对照组)"),
    dict(cid=7,  name="门限扫描 conf=0.35",   kind="file", target="sim_demo_simft.mp4",
         conf=0.35, size=0.270, min_lock=None, note="敏感性实验不设合格线(中门限)"),
    dict(cid=8,  name="门限扫描 conf=0.50",   kind="file", target="sim_demo_simft.mp4",
         conf=0.50, size=0.270, min_lock=None, note="敏感性实验不设合格线(高门限)"),
    dict(cid=9,  name="尺寸敏感 size=0.230",  kind="file", target="sim_recorded.mp4",
         conf=0.20, size=0.230, min_lock=None, note="偏小尺寸→测距系统性偏大"),
    dict(cid=10, name="尺寸敏感 size=0.310",  kind="file", target="sim_recorded.mp4",
         conf=0.20, size=0.310, min_lock=None, note="偏大尺寸→测距系统性偏小"),
    dict(cid=11, name="TCP实时链路 第1轮(遮挡场景)", kind="tcp", target="tcp_live",
         conf=0.20, size=0.270, min_lock=None, min_track=0.70,
         note="jMAVSim 随机航迹+遮挡物, 合格线=航迹保持率70%"),
    dict(cid=12, name="TCP实时链路 第2轮(遮挡场景)", kind="tcp", target="tcp_live",
         conf=0.20, size=0.270, min_lock=None, min_track=0.70,
         note="jMAVSim 随机航迹+遮挡物, 合格线=航迹保持率70%"),
    dict(cid=13, name="TCP实时链路 第3轮(遮挡场景)", kind="tcp", target="tcp_live",
         conf=0.20, size=0.270, min_lock=None, min_track=0.70,
         note="jMAVSim 随机航迹+遮挡物, 合格线=航迹保持率70%"),
    dict(cid=14, name="真实摄像头",           kind="camera", target="0",
         conf=0.20, size=0.270, min_lock=None, note="需外接摄像头, 默认跳过"),
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_only(spec):
    ids = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ids.update(range(int(a), int(b) + 1))
        elif part:
            ids.add(int(part))
    return ids


def tcp_alive(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_case(case, detector, args):
    """返回 (status, metrics, csv_path); status ∈ done/skipped/failed。"""
    cid, kind = case["cid"], case["kind"]
    csv_name = f"case{cid:02d}_{case['target'].replace('.', '_')}.csv"
    csv_path = os.path.join(OUT_DIR, csv_name)

    # ---- 用例前置检查(可解释的跳过原因) ----
    if kind == "file":
        target_path = os.path.join(BASE, case["target"])
        if not os.path.isfile(target_path):
            return "skipped", {"skip_reason": "录像文件不存在"}, None
        cap = cv2.VideoCapture(target_path)
        if not cap.isOpened():
            cap.release()
            return "skipped", {"skip_reason": "录像无法打开"}, None
        start = int(case.get("start", 0))
        if start:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    elif kind == "tcp":
        host, _, port = args.tcp.partition(":")
        host, port = host.strip(), int(port or 14590)
        if not tcp_alive(host, port):
            return "skipped", {"skip_reason": f"TCP帧服务 {host}:{port} 未启动"}, None
        cap = TcpFrameSource(host, port)
    else:
        if not args.camera:
            return "skipped", {"skip_reason": "摄像头用例默认跳过(加 --camera 启用)"}, None
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap.release()
            return "skipped", {"skip_reason": "未检测到可用摄像头"}, None

    # ---- 重置检测链路状态, 套用本用例参数 ----
    detector.reset_stats()
    detector._reset_track()
    detector.set_conf_threshold(case["conf"])
    detector.set_drone_size(case["size"])

    counts = {"LOCKED": 0, "COAST": 0, "SEARCHING": 0}
    confs, zs = [], []
    first_lock_ms = None
    n = 0
    t_first = None
    t_prev = None
    ema_fps = 0.0
    deadline = None if kind != "tcp" else time.time() + args.wait_first
    max_frames = args.frames if kind == "file" else 10 ** 9

    fcsv = open(csv_path, "w", buffering=1, newline="", encoding="utf-8")
    wcsv = csv.writer(fcsv)
    wcsv.writerow(CSV_HEADER)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if kind == "tcp":
                    if time.time() > deadline:
                        break
                    continue
                break           # 文件读完/摄像头断开
            now = time.time()
            if t_first is None:
                t_first = now
                if kind == "tcp":
                    deadline = now + args.tcp_seconds
            if t_prev is not None and now > t_prev:
                ema_fps = 0.9 * ema_fps + 0.1 / (now - t_prev) if ema_fps \
                    else 1.0 / (now - t_prev)
            t_prev = now
            if kind == "tcp" and now > deadline:
                break
            if n >= max_frames:
                break

            overlay, d = detector.detect(frame)
            st = d.get("status", "SEARCHING")
            counts[st] = counts.get(st, 0) + 1
            n += 1
            ts_ms = int((now - t_first) * 1000)
            if st == "LOCKED":
                if first_lock_ms is None:
                    first_lock_ms = ts_ms
                confs.append(d.get("conf", 0.0))
            if d.get("tracked"):
                zs.append(d.get("z_akf", 0.0))
            wcsv.writerow([
                detector.total_frames, ts_ms, st,
                int(bool(d.get("det"))), int(bool(d.get("tracked"))),
                f"{d.get('conf', 0):.3f}",
                d.get("x1", 0), d.get("y1", 0), d.get("x2", 0), d.get("y2", 0),
                f"{d.get('box_w', 0):.1f}", f"{d.get('box_h', 0):.1f}",
                f"{d.get('z_raw', 0):.3f}", f"{d.get('z_akf', 0):.3f}",
                f"{d.get('z_pred', 0):.3f}",
                f"{d.get('azim', 0):.3f}", f"{d.get('elev', 0):.3f}",
                f"{ema_fps:.1f}", case["target"],
            ])
    except Exception as e:
        fcsv.close()
        cap.release()
        return "failed", {"error": f"{type(e).__name__}: {e}",
                          "trace": traceback.format_exc()}, csv_path
    fcsv.close()
    cap.release()

    if n == 0:
        return "skipped", {"skip_reason": "未取到任何帧"}, csv_path

    dur = max(time.time() - t_first, 1e-6)
    ca = np.array(confs) if confs else np.array([0.0])
    za = np.array(zs) if zs else np.array([0.0])
    lock_rate = counts["LOCKED"] / n
    track_rate = (counts["LOCKED"] + counts["COAST"]) / n
    passed = None
    if case.get("min_track") is not None:
        # 遮挡场景: 合格线看航迹保持率(LOCKED+COAST), 而非纯锁定率
        passed = first_lock_ms is not None and track_rate >= case["min_track"]
    elif case["min_lock"] is not None:
        passed = first_lock_ms is not None and lock_rate >= case["min_lock"]
    m = dict(
        frames=n, locked=counts["LOCKED"], coast=counts["COAST"],
        search=counts["SEARCHING"],
        lock_rate=lock_rate, track_rate=track_rate,
        first_lock_s=(first_lock_ms / 1000.0 if first_lock_ms is not None else None),
        conf_mean=float(ca.mean()), conf_min=float(ca.min()), conf_max=float(ca.max()),
        z_min=float(za.min()), z_mean=float(za.mean()), z_max=float(za.max()),
        fps=n / dur, passed=passed, csv=os.path.basename(csv_path),
        csv_rows=n,
    )
    return "done", m, csv_path


def atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_summaries(results):
    # ---- summary.csv ----
    fields = ["cid", "name", "kind", "target", "conf", "size", "status",
              "frames", "locked", "coast", "search", "lock_rate", "track_rate",
              "first_lock_s", "conf_mean", "z_min", "z_mean", "z_max", "fps",
              "verdict", "skip_reason", "error", "csv"]
    with open(os.path.join(OUT_DIR, "summary.csv.tmp"), "w",
              newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        for c, status, m in results:
            row = {k: "" for k in fields}
            row.update(cid=c["cid"], name=c["name"], kind=c["kind"],
                       target=c["target"], conf=c["conf"], size=c["size"],
                       status=status)
            if status == "done":
                row.update({k: m.get(k, "") for k in
                            ("frames", "locked", "coast", "search",
                             "lock_rate", "track_rate", "first_lock_s",
                             "conf_mean", "z_min", "z_mean", "z_max", "fps", "csv")})
                row["verdict"] = ("PASS" if m["passed"] else
                                  "FAIL" if m["passed"] is False else "--")
            elif status == "skipped":
                row["verdict"] = "SKIP"
                row["skip_reason"] = m.get("skip_reason", "")
            else:
                row["verdict"] = "ERROR"
                row["error"] = m.get("error", "")
            wr.writerow(row)
    os.replace(os.path.join(OUT_DIR, "summary.csv.tmp"),
               os.path.join(OUT_DIR, "summary.csv"))

    # ---- summary.md(中文论文表) ----
    lines = [
        "# 14 用例批量测试汇总",
        "",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 用例 | 名称 | 源 | 门限 | 尺寸(m) | 帧数 | 锁定率 | 航迹保持率 | 首锁(s) | 置信度均值 | 距离范围(m) | 处理fps | 结论 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c, status, m in results:
        if status == "done":
            zrng = f"{m['z_min']:.1f}~{m['z_max']:.1f}" if m["locked"] else "--"
            fl = f"{m['first_lock_s']:.2f}" if m["first_lock_s"] is not None else "未锁"
            verdict = ("✅PASS" if m["passed"] else
                       "❌FAIL" if m["passed"] is False else "—")
            lines.append(
                f"| C{c['cid']:02d} | {c['name']} | {c['target']} | "
                f"{c['conf']:.2f} | {c['size']:.3f} | {m['frames']} | "
                f"{m['lock_rate']*100:.1f}% | {m['track_rate']*100:.1f}% | "
                f"{fl} | {m['conf_mean']:.3f} | {zrng} | {m['fps']:.1f} | {verdict} |")
        elif status == "skipped":
            lines.append(
                f"| C{c['cid']:02d} | {c['name']} | {c['target']} | "
                f"{c['conf']:.2f} | {c['size']:.3f} | - | - | - | - | - | - | - | "
                f"⏭跳过({m.get('skip_reason','')}) |")
        else:
            lines.append(
                f"| C{c['cid']:02d} | {c['name']} | {c['target']} | "
                f"{c['conf']:.2f} | {c['size']:.3f} | - | - | - | - | - | - | - | "
                f"⚠错误({m.get('error','')}) |")
    n_done = sum(1 for _, s, _ in results if s == "done")
    n_pass = sum(1 for _, s, m in results if s == "done" and m["passed"] is True)
    n_fail = sum(1 for _, s, m in results if s == "done" and m["passed"] is False)
    n_skip = sum(1 for _, s, _ in results if s == "skipped")
    n_err = sum(1 for _, s, _ in results if s == "failed")
    lines += ["",
              f"**统计: 计划 {len(results)} 例, 完成 {n_done}, "
              f"PASS {n_pass}, FAIL {n_fail}, 跳过 {n_skip}, 错误 {n_err}**",
              "",
              "说明: 锁定率=LOCKED帧占比(真实量测); 航迹保持率=LOCKED+COAST占比"
              "(含1.0s预测外推)。",
              "C01-C03 为录像基线(合格线=锁定率80%); C11-C13 为TCP遮挡场景"
              "(合格线=航迹保持率70%, 含COAST预测外推); C04-C10 为特性刻画用例"
              "(真实场景/门限扫描/尺寸敏感), 结论 `--` 表示仅统计不判定。",
              ""]
    atomic_write(os.path.join(OUT_DIR, "summary.md"), "\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="DRLS 14 用例批量测试")
    ap.add_argument("--only", default="", help="只用例号, 如 1-10 或 1,3,11-13")
    ap.add_argument("--frames", type=int, default=900, help="离线用例最大帧数")
    ap.add_argument("--tcp-seconds", type=float, default=20.0, help="TCP每轮秒数")
    ap.add_argument("--wait-first", type=float, default=12.0, help="TCP等首帧秒数")
    ap.add_argument("--tcp", default="127.0.0.1:14590", help="TCP帧服务地址")
    ap.add_argument("--camera", action="store_true", help="启用摄像头用例")
    args = ap.parse_args()

    only = parse_only(args.only) if args.only else None
    selected = [c for c in CASES if only is None or c["cid"] in only]
    if not selected:
        log("没有匹配的用例号"); sys.exit(2)

    os.makedirs(OUT_DIR, exist_ok=True)
    log(f"计划用例 {len(selected)} 个: {[c['cid'] for c in selected]}")
    log("加载模型(只加载一次, 后续用例复用)...")
    detector = DroneDetector()
    t0 = time.time()
    detector.load_model()
    log(f"模型就绪, 耗时 {time.time()-t0:.1f}s")

    results = []
    skip_reasons = {}
    for c in selected:
        log(f"--- C{c['cid']:02d} {c['name']} | {c['target']} | "
            f"conf={c['conf']:.2f} size={c['size']:.3f}")
        t = time.time()
        status, m, csv_path = run_case(c, detector, args)
        results.append((c, status, m))
        if status == "done":
            verdict = ("PASS" if m["passed"] else
                       "FAIL" if m["passed"] is False else "--")
            log(f"    -> {verdict}  {m['frames']}帧 锁定率"
                f"{m['lock_rate']*100:.1f}% 保持率{m['track_rate']*100:.1f}% "
                f"首锁={m['first_lock_s']} conf={m['conf_mean']:.3f} "
                f"z={m['z_min']:.1f}~{m['z_max']:.1f}m {m['fps']:.1f}fps "
                f"({time.time()-t:.0f}s) -> {m['csv']}")
        elif status == "skipped":
            r = m.get("skip_reason", "?")
            skip_reasons[r] = skip_reasons.get(r, 0) + 1
            log(f"    -> SKIP: {r}")
        else:
            log(f"    -> ERROR: {m.get('error')}")
            if os.environ.get("VERBOSE"):
                print(m.get("trace", ""))

    write_summaries(results)
    n_done = sum(1 for _, s, _ in results if s == "done")
    n_pass = sum(1 for _, s, m in results if s == "done" and m["passed"] is True)
    n_fail = sum(1 for _, s, m in results if s == "done" and m["passed"] is False)
    n_skip = sum(1 for _, s, _ in results if s == "skipped")
    n_err = sum(1 for _, s, _ in results if s == "failed")
    log("================ 汇总 ================")
    log(f"计划 {len(results)} | 完成 {n_done} | PASS {n_pass} | "
        f"FAIL {n_fail} | 跳过 {n_skip} | 错误 {n_err}")
    for r, k in skip_reasons.items():
        log(f"  跳过原因: {r} × {k}")
    log(f"明细: {OUT_DIR}/summary.csv")
    log(f"论文表: {OUT_DIR}/summary.md")
    sys.exit(1 if (n_fail or n_err) else 0)


if __name__ == "__main__":
    main()
