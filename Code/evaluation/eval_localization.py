#!/usr/bin/env python3
"""
E3 / E3b / E3c 离线评测 —— 论文第4章三张对比表自动生成

前提: calibration/intrinsics.json 已生成；selfdata/meta.json 已登记采集片段
  E3  定位精度: 各距离档 RMSE(真值=卷尺) + 抖动std，对比 单帧/滑动平均/标准KF/AKF
  E3b 预测精度: 移动序列 ADE@0.5/1/2s(伪真值=离线PnP)，对比 匀速外推/AKF预测
  E3c 角度精度: 静止片段 方位/俯仰 MAE(真值=meta 或 0)，对比 单帧/AKF平滑

用法:  python eval_localization.py            # 全部评测
       python eval_localization.py --e3       # 只跑 E3
       python eval_localization.py --e3b --e3c
输出:  report_materials/e3_table.md / e3b_table.md / e3c_table.md
"""
import argparse
import json
import os

import cv2
import numpy as np

from akf_demo import AdaptiveKalmanFilter

BASE = os.path.dirname(os.path.abspath(__file__))
TAG_SIZE = 0.16
WARMUP = 10          # 滤波预热帧（不计入指标）
MA_WIN = 15          # 滑动平均窗口
OBJ_PTS = np.array([[-TAG_SIZE/2, -TAG_SIZE/2, 0], [TAG_SIZE/2, -TAG_SIZE/2, 0],
                    [TAG_SIZE/2,  TAG_SIZE/2, 0], [-TAG_SIZE/2,  TAG_SIZE/2, 0]],
                   dtype=np.float64)


# ---------------- 基础工具 ----------------
def load_intrinsics():
    path = os.path.join(BASE, "calibration", "intrinsics.json")
    if not os.path.exists(path):
        raise SystemExit(f"[!] 缺少 {path}，请先运行 calibrate_camera.py")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return np.array(d["camera_matrix"]), np.array(d["dist_coeffs"])


def make_detector():
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    return cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())


def extract_sequence(video, K, dist, detector):
    """逐帧 PnP -> [(t, x, y, z, az_deg, el_deg), ...]，t 为帧号/fps"""
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    seq = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is not None and len(ids) > 0:
            ok2, rvec, tvec = cv2.solvePnP(
                OBJ_PTS, corners[0][0].astype(np.float64), K, dist)
            if ok2:
                x, y, z = tvec.flatten()
                seq.append((i / fps, x, y, z,
                            np.degrees(np.arctan2(x, z)),
                            np.degrees(np.arctan2(-y, z))))
        i += 1
    cap.release()
    return seq, fps


class StandardKF(AdaptiveKalmanFilter):
    """标准 KF：与 AKF 同结构但 R 固定（消融对比用）"""
    def update(self, z):
        if not self.initialized:
            self.x[:3] = z
            self.initialized = True
            return self.x[:3].copy()
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P
        return self.x[:3].copy()          # 不做 R 自适应


def run_filter(seq, cls, **kw):
    """对序列跑滤波，返回与 seq 等长的平滑 3D 位置数组（含未检出帧外推）"""
    f = cls(**kw)
    dt = 1.0 / 30.0
    out = np.full((len(seq), 3), np.nan)
    for i, s in enumerate(seq):
        t = s[0]
        if i > 0:
            dt = t - seq[i - 1][0]
        f.predict(dt)
        pos = f.update(np.array(s[1:4]))
        out[i] = pos
    return out


def moving_avg(seq, win=MA_WIN):
    arr = np.array([s[1:4] for s in seq])
    out = np.full_like(arr, np.nan)
    for i in range(len(arr)):
        j0 = max(0, i - win + 1)
        out[i] = arr[j0:i + 1].mean(axis=0)
    return out


# ---------------- E3: 定位精度 ----------------
def eval_e3(meta, K, dist, detector):
    rows = {}
    for e in meta:
        if e.get("mode") != "static" or "true_distance_m" not in e:
            continue
        video = os.path.join(BASE, e["file"])
        seq, _ = extract_sequence(video, K, dist, detector)
        if len(seq) < WARMUP + 20:
            print(f"[跳过] {e['file']} 有效帧不足({len(seq)})")
            continue
        d_true = e["true_distance_m"]
        raw = np.array([np.linalg.norm(s[1:4]) for s in seq])
        akf = np.linalg.norm(run_filter(seq, AdaptiveKalmanFilter, alpha=0.12, q_scale=0.008)[WARMUP:], axis=1)
        stk = np.linalg.norm(run_filter(seq, StandardKF, alpha=0.12, q_scale=0.008)[WARMUP:], axis=1)
        mavg = np.linalg.norm(moving_avg(seq)[WARMUP:], axis=1)
        raw_w = raw[WARMUP:]
        row = {
            "raw_rmse": np.sqrt(np.mean((raw_w - d_true) ** 2)),
            "ma_rmse": np.sqrt(np.mean((mavg - d_true) ** 2)),
            "kf_rmse": np.sqrt(np.mean((stk - d_true) ** 2)),
            "akf_rmse": np.sqrt(np.mean((akf - d_true) ** 2)),
            "raw_std": float(np.std(raw_w)),
            "akf_std": float(np.std(akf)),
            "n": len(seq),
        }
        rows.setdefault(d_true, []).append(row)
        print(f"E3 {e['file']}: d={d_true}m raw={row['raw_rmse']:.3f} "
              f"AKF={row['akf_rmse']:.3f} (n={row['n']})")

    lines = ["# E3 定位精度（自采 AprilTag 序列，真值=卷尺）", "",
             "| 距离(m) | 单帧RMSE | 滑动平均 | 标准KF | **AKF** | 单帧抖动σ | AKF抖动σ | 帧数 |",
             "|---------|---------|---------|--------|---------|-----------|----------|------|"]
    agg = {}
    for d_true, rs in sorted(rows.items()):
        m = {k: float(np.mean([r[k] for r in rs])) for k in rs[0]}
        agg[d_true] = m
        lines.append(f"| {d_true:.2f} | {m['raw_rmse']:.3f} | {m['ma_rmse']:.3f} | "
                     f"{m['kf_rmse']:.3f} | **{m['akf_rmse']:.3f}** | "
                     f"{m['raw_std']:.4f} | {m['akf_std']:.4f} | {m['n']:.0f} |")
    if agg:
        n = len(agg)
        avg = {k: sum(m[k] for m in agg.values()) / n for k in next(iter(agg.values()))}
        lines.append(f"| **均值** | {avg['raw_rmse']:.3f} | {avg['ma_rmse']:.3f} | "
                     f"{avg['kf_rmse']:.3f} | **{avg['akf_rmse']:.3f}** | "
                     f"{avg['raw_std']:.4f} | {avg['akf_std']:.4f} | - |")
    out = os.path.join(BASE, "report_materials", "e3_table.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] {out}")


# ---------------- E3b: 预测精度 ----------------
def eval_e3b(meta, K, dist, detector):
    horizons = [0.5, 1.0, 2.0]
    res_cv = {h: [] for h in horizons}
    res_akf = {h: [] for h in horizons}
    for e in meta:
        if e.get("mode") != "moving":
            continue
        video = os.path.join(BASE, e["file"])
        seq, fps = extract_sequence(video, K, dist, detector)
        if len(seq) < 60:
            print(f"[跳过] {e['file']} 有效帧不足({len(seq)})")
            continue
        gt = np.array([s[1:4] for s in seq])           # 伪真值 = 离线PnP
        ts = np.array([s[0] for s in seq])
        f = AdaptiveKalmanFilter(alpha=0.12, q_scale=0.008)
        states = np.full((len(seq), 6), np.nan)
        for i, s in enumerate(seq):
            dt = s[0] - seq[i - 1][0] if i else 1 / fps
            f.predict(dt)
            states[i] = f.update(np.array(s[1:4]))
        for h in horizons:
            for i in range(WARMUP, len(seq)):
                j = np.searchsorted(ts, ts[i] + h)
                if j >= len(seq):
                    break
                # 匀速外推：最近 MA_WIN 帧平均速度
                j0 = max(0, i - MA_WIN + 1)
                if ts[i] > ts[j0]:
                    v = (gt[i] - gt[j0]) / (ts[i] - ts[j0])
                else:
                    v = np.zeros(3)
                cv_pred = gt[i] + v * h
                akf_pred = states[i, :3] + states[i, 3:] * h
                res_cv[h].append(np.linalg.norm(cv_pred - gt[j]))
                res_akf[h].append(np.linalg.norm(akf_pred - gt[j]))
    lines = ["# E3b 短期预测精度（ADE，移动 AprilTag 序列，伪真值=离线PnP）", "",
             "| 预测时域 | 匀速外推 ADE(m) | **窗口+AKF 预测 ADE(m)** | 改善 | 样本数 |",
             "|----------|----------------|--------------------------|------|--------|"]
    for h in horizons:
        if not res_cv[h]:
            continue
        cv_m = float(np.mean(res_cv[h]))
        akf_m = float(np.mean(res_akf[h]))
        imp = (cv_m - akf_m) / cv_m * 100
        lines.append(f"| {h:.1f}s | {cv_m:.3f} | **{akf_m:.3f}** | {imp:+.1f}% | {len(res_cv[h])} |")
    out = os.path.join(BASE, "report_materials", "e3b_table.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] {out}")


# ---------------- E3c: 角度精度 ----------------
def eval_e3c(meta, K, dist, detector):
    rows = []
    for e in meta:
        if e.get("mode") != "static":
            continue
        video = os.path.join(BASE, e["file"])
        seq, _ = extract_sequence(video, K, dist, detector)
        if len(seq) < WARMUP + 20:
            continue
        az = np.array([s[4] for s in seq])
        el = np.array([s[5] for s in seq])
        pos = run_filter(seq, AdaptiveKalmanFilter, alpha=0.12, q_scale=0.008)
        az_akf = np.degrees(np.arctan2(pos[WARMUP:, 0], pos[WARMUP:, 2]))
        el_akf = np.degrees(np.arctan2(-pos[WARMUP:, 1], pos[WARMUP:, 2]))
        # 真值：meta 指定或默认标架正对=0
        az_true = np.radians(e.get("azimuth_deg", 0.0))
        el_true = np.radians(e.get("elevation_deg", 0.0))
        rows.append({
            "az_raw": float(np.mean(np.abs(np.radians(az[WARMUP:]) - az_true))),
            "az_akf": float(np.mean(np.abs(np.radians(az_akf) - az_true))),
            "el_raw": float(np.mean(np.abs(np.radians(el[WARMUP:]) - el_true))),
            "el_akf": float(np.mean(np.abs(np.radians(el_akf) - el_true))),
        })
    if not rows:
        print("[E3c] 无 static 片段可评")
        return
    m = {k: float(np.degrees(np.mean([r[k] for r in rows]))) for k in rows[0]}
    lines = ["# E3c 角度精度（MAE，自采 AprilTag 序列）", "",
             "| 方法 | 方位角 MAE(°) | 俯仰角 MAE(°) |",
             "|------|--------------|--------------|",
             f"| 单帧原始 | {m['az_raw']:.3f} | {m['el_raw']:.3f} |",
             f"| **AKF 平滑** | **{m['az_akf']:.3f}** | **{m['el_akf']:.3f}** |", "",
             f"注: 真值角默认 0°（三脚架正对标架），共 {len(rows)} 段。"]
    out = os.path.join(BASE, "report_materials", "e3c_table.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--e3", action="store_true")
    ap.add_argument("--e3b", action="store_true")
    ap.add_argument("--e3c", action="store_true")
    ap.add_argument("--all", action="store_true", default=True)
    args = ap.parse_args()

    meta_path = os.path.join(BASE, "selfdata", "meta.json")
    if not os.path.exists(meta_path):
        raise SystemExit("[!] 尚无采集数据: 先运行 collect_apriltag.py")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    K, dist = load_intrinsics()
    detector = make_detector()
    print(f"已登记 {len(meta)} 个片段")

    run_all = args.all and not (args.e3 or args.e3b or args.e3c)
    if args.e3 or run_all:
        eval_e3(meta, K, dist, detector)
    if args.e3b or run_all:
        eval_e3b(meta, K, dist, detector)
    if args.e3c or run_all:
        eval_e3c(meta, K, dist, detector)


if __name__ == "__main__":
    main()
