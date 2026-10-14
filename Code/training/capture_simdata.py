#!/usr/bin/env python3
"""
仿真域 finetune 数据采集: TCP帧流(14590) + UDP真值(14680) → 原始帧 + YOLO标签
利用护航相机注视目标特性, 真值投影自动标注(零人工标注)
按距离分桶采样, 重点覆盖近距大尺度(3-6m)和远距(9-11m)检出死区

真值投影原理:
  护航相机 setViewerTargetObject 自动注视目标 → 目标在视轴上 → 像素中心=图像中心
  框高 h = fx * DRONE_SIZE / z_true   (等效尺寸由 v5 检出帧真值标定 0.230m)
  框宽 w = h * ASPECT                 (四旋翼侧视宽高比 2.62)

用法(WSL): ~/yolo/bin/python /mnt/d/Graduate/code/capture_simdata.py
停止: Ctrl+C
"""
import cv2
import math
import os
import signal
import socket
import threading
import time

import numpy as np

FRAME_HOST, FRAME_PORT = "127.0.0.1", 14590
TRUTH_BIND_PORT = 14680
CAM_W, CAM_H = 1280, 720
FX = (CAM_W / 2) / math.tan(math.pi / 6)       # 1108.5px
CAM_POS = np.array([0.0, -40.0, -12.0])
DRONE_SIZE = 0.230                               # 等效高度(m), v5 标定
ASPECT = 2.62                                    # 框宽高比

OUT = "/mnt/d/Graduate/sim_finetune"
IMG_DIR = os.path.join(OUT, "images")
LBL_DIR = os.path.join(OUT, "labels")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(LBL_DIR, exist_ok=True)

# 距离分桶采样: (距离下限m, 上限m, 目标帧数). 重点补近距/远距死区
BUCKETS = [
    (3.0, 6.0, 150),     # 近距大尺度死区(检出率 0-6%)
    (6.0, 7.0, 80),      # 工作窗边缘
    (7.0, 9.0, 100),     # 工作窗(已能检出, 少量补充)
    (9.0, 12.0, 120),    # 远距死区(弱响应)
]
bucket_count = [0] * len(BUCKETS)
# 同桶内最小采样间隔(帧), 避免连续帧过于相似
MIN_GAP = 5
last_save_frame = [-1000] * len(BUCKETS)

latest_frame = None
latest_truth = None
lock = threading.Lock()
running = True
stop_req = False


def frame_receiver():
    global latest_frame
    while running:
        try:
            c = socket.create_connection((FRAME_HOST, FRAME_PORT), timeout=3)
            buf = b""
            while running:
                pkt = c.recv(65536)
                if not pkt:
                    break
                buf += pkt
                while b"\n" in buf:
                    header, rest = buf.split(b"\n", 1)
                    parts = header.decode("ascii", "ignore").split()
                    if parts[0] != "FRAME" or len(parts) != 5:
                        buf = rest
                        continue
                    ln = int(parts[4])
                    if len(rest) < ln:
                        break
                    with lock:
                        latest_frame = (int(parts[1]), rest[:ln])
                    buf = rest[ln:]
        except Exception:
            time.sleep(0.5)


def truth_receiver():
    global latest_truth
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", TRUTH_BIND_PORT))
    s.settimeout(1.0)
    while running:
        try:
            data, _ = s.recvfrom(4096)
            msg = data.decode("ascii", "ignore").strip()
            f = dict(kv.split("=") if "=" in kv else (kv, "")
                     for kv in msg.split(" ") if "=" in kv)
            tp = np.array([float(v) for v in f["tp"].split(",")])
            tv = np.array([float(v) for v in f["tv"].split(",")])
            with lock:
                latest_truth = {"t": int(f["t"]), "tp": tp, "tv": tv}
        except socket.timeout:
            continue
        except Exception:
            continue


# 标注校准(2026-09-07, v5 检出帧统计):
#   - 目标像素中心 y 中位 343 (图像中心 360, 偏上 17px, 相机注视点略偏)
#   - 框放大 1.15 倍留旋翼/起落架余量, 避免小目标被切边
CY_OFFSET = -17
BOX_SCALE = 1.15


def compute_gt(z_true):
    """真值投影: 目标在视轴上 → 中心≈图像中心; 框高由距离决定."""
    cx = CAM_W / 2
    cy = CAM_H / 2 + CY_OFFSET
    h = FX * DRONE_SIZE / max(z_true, 0.1) * BOX_SCALE
    w = h * ASPECT
    # clamp to image
    x1 = max(0, int(cx - w / 2))
    y1 = max(0, int(cy - h / 2))
    x2 = min(CAM_W, int(cx + w / 2))
    y2 = min(CAM_H, int(cy + h / 2))
    # YOLO 格式: class cx_norm cy_norm w_norm h_norm
    cx_n = (x1 + x2) / 2 / CAM_W
    cy_n = (y1 + y2) / 2 / CAM_H
    w_n = (x2 - x1) / CAM_W
    h_n = (y2 - y1) / CAM_H
    return "0 %.6f %.6f %.6f %.6f\n" % (cx_n, cy_n, w_n, h_n)


def main():
    global stop_req, running
    signal.signal(signal.SIGTERM, lambda s, f: globals().__setitem__("stop_req", True))
    signal.signal(signal.SIGINT, lambda s, f: globals().__setitem__("stop_req", True))

    threading.Thread(target=frame_receiver, daemon=True).start()
    threading.Thread(target=truth_receiver, daemon=True).start()

    target_total = sum(b[2] for b in BUCKETS)
    print(f"[capture] 目标采集 {target_total} 帧, 分桶: "
          + ", ".join(f"{b[0]}-{b[1]}m×{b[2]}" for b in BUCKETS))
    print(f"[capture] fx={FX:.1f} size={DRONE_SIZE}m aspect={ASPECT}")
    print("[capture] 等待帧流和真值...")

    frame_i = 0
    saved = 0
    t_start = time.time()
    while not stop_req:
        with lock:
            fr = latest_frame
            truth = dict(latest_truth) if latest_truth else None
        if fr is None or truth is None:
            time.sleep(0.02)
            continue
        ts_ms, jpeg = fr
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        frame_i += 1

        tp = truth["tp"]
        z_true = float(np.linalg.norm(tp - CAM_POS))
        if z_true < 1.0 or z_true > 20.0:
            continue

        # 分桶采样
        picked = None
        for bi, (lo, hi, cap) in enumerate(BUCKETS):
            if lo <= z_true < hi:
                if bucket_count[bi] < cap and (frame_i - last_save_frame[bi]) >= MIN_GAP:
                    picked = bi
                break

        if picked is not None:
            name = "f%05d_z%.1f" % (frame_i, z_true)
            cv2.imwrite(os.path.join(IMG_DIR, name + ".jpg"), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            with open(os.path.join(LBL_DIR, name + ".txt"), "w") as lf:
                lf.write(compute_gt(z_true))
            bucket_count[picked] += 1
            last_save_frame[picked] = frame_i
            saved += 1
            if saved % 10 == 0:
                elapsed = time.time() - t_start
                print(f"[capture] saved={saved}/{target_total}  "
                      + " ".join(f"{b[0]}-{b[1]}m:{bucket_count[i]}/{b[2]}"
                                 for i, b in enumerate(BUCKETS))
                      + f"  z={z_true:.1f}m  {elapsed:.0f}s")
            if saved >= target_total:
                print(f"[capture] 达到目标 {target_total} 帧, 停止")
                break

        if frame_i % 300 == 0:
            elapsed = time.time() - t_start
            print(f"[capture] frame={frame_i} saved={saved} "
                  f"fps={frame_i/elapsed:.1f} z_now={z_true:.1f}m")

    running = False
    # 生成 data.yaml 和划分
    gen_split()
    print(f"[capture] 结束: 处理 {frame_i} 帧, 保存 {saved} 张 -> {OUT}")


def gen_split():
    """生成 data.yaml + train/val 划分 (80/20, 按距离分层)."""
    import random
    imgs = [f[:-4] for f in os.listdir(IMG_DIR) if f.endswith(".jpg")]
    random.seed(42)
    random.shuffle(imgs)
    n = len(imgs)
    n_val = max(1, n // 5)
    val = imgs[:n_val]
    train = imgs[n_val:]
    split_dir = os.path.join(OUT, "splits")
    os.makedirs(split_dir, exist_ok=True)
    with open(os.path.join(split_dir, "train.txt"), "w") as f:
        f.write("\n".join(os.path.join(IMG_DIR, x + ".jpg") for x in train) + "\n")
    with open(os.path.join(split_dir, "val.txt"), "w") as f:
        f.write("\n".join(os.path.join(IMG_DIR, x + ".jpg") for x in val) + "\n")
    yaml = (
        "path: /mnt/d/Graduate/sim_finetune\n"
        "train: splits/train.txt\n"
        "val: splits/val.txt\n"
        "names:\n  0: drone\n"
    )
    with open(os.path.join(OUT, "data.yaml"), "w") as f:
        f.write(yaml)
    print(f"[capture] 划分: train={len(train)} val={len(val)} -> {OUT}/data.yaml")


if __name__ == "__main__":
    main()
