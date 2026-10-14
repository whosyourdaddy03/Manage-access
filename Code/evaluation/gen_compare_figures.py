#!/usr/bin/env python3
"""
生成检测对比图：基线漏检 vs 本文方法（+P2+EMA）检出，并排保存
选帧策略：验证集中 基线低置信/漏检 且 本文方法高置信 的帧，按目标面积极小优先

用法: ~/yolo/bin/python gen_compare_figures.py [n_out]
输出: report_materials/compare_01.jpg ... （并排图，可直接进论文/汇报PPT）
"""
import os
import sys

import cv2
import numpy as np
from ultralytics import YOLO

VAL_DIR = "/mnt/d/Graduate/code/dataset/detfly/images/val"
BASE_PT = "/mnt/d/Graduate/code/runs/preview_v8n-4/weights/best.pt"
OURS_PT = "/mnt/d/Graduate/code/runs/p2ema_v8n/weights/best.pt"
LBL_DIR = "/mnt/d/Graduate/code/dataset/detfly/labels/val"
OUT_DIR = "/mnt/d/Graduate/code/report_materials"

N_OUT = int(sys.argv[1]) if len(sys.argv) > 1 else 4
N_SCAN = 300          # 扫描前 N 张验证图
CONF_SHOW = 0.25      # 展示阈值（低于此不算检出）

mb = YOLO(BASE_PT)
mo = YOLO(OURS_PT)

files = sorted(f for f in os.listdir(VAL_DIR) if f.lower().endswith(".jpg"))[:N_SCAN]


def gt_boxes(f, W, H):
    lbl = os.path.join(LBL_DIR, os.path.splitext(f)[0] + ".txt")
    out = []
    if os.path.exists(lbl):
        for line in open(lbl):
            c, cx, cy, bw, bh = map(float, line.split())
            out.append((int((cx - bw / 2) * W), int((cy - bh / 2) * H),
                        int(bw * W), int(bh * H)))
    return out


def draw(img, boxes, confs, label, color):
    disp = img.copy()
    for (x1, y1, x2, y2), cf in zip(boxes, confs):
        cv2.rectangle(disp, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        cv2.putText(disp, f"UAV {cf:.2f}", (int(x1), int(y1) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(disp, label, (20, 60), cv2.FONT_HERSHEY_SIMPLEX,
                1.6, color, 3)
    return disp


cands = []
for n, f in enumerate(files):
    p = os.path.join(VAL_DIR, f)
    img = cv2.imread(p)
    H, W = img.shape[:2]
    rb = mb.predict(p, imgsz=640, conf=0.05, verbose=False, device=0)[0]
    ro = mo.predict(p, imgsz=640, conf=0.05, verbose=False, device=0)[0]
    # 基线最大置信度（0.05 阈值下）
    cb = float(rb.boxes.conf.max()) if len(rb.boxes) else 0.0
    co = float(ro.boxes.conf.max()) if len(ro.boxes) else 0.0
    if co < 0.5:
        continue                       # 本文方法至少要可靠检出
    # 最小 GT 目标面积占比（越小越能体现 P2 价值）
    gts = gt_boxes(f, W, H)
    if not gts:
        continue
    frac = min(g[2] * g[3] for g in gts) / (W * H)
    gap = co - cb                      # 置信度差最大 = 两模型分化最明显的帧
    cands.append((-gap, frac, n, f))
    if (n + 1) % 50 == 0:
        print(f"scanned {n+1}/{len(files)}, candidates={len(cands)}")

cands.sort()
print(f"共 {len(cands)} 个候选帧，取 {N_OUT} 张")

os.makedirs(OUT_DIR, exist_ok=True)
made = 0
for frac, _, _, f in cands:
    if made >= N_OUT:
        break
    p = os.path.join(VAL_DIR, f)
    img = cv2.imread(p)
    H, W = img.shape[:2]
    gts = gt_boxes(f, W, H)
    panels = []
    for model, pt_name, color, tag in [
        (mb, BASE_PT, (0, 0, 255), "YOLOv8n baseline"),
        (mo, OURS_PT, (0, 220, 0), "Ours (+P2+EMA)"),
    ]:
        r = model.predict(p, imgsz=640, conf=CONF_SHOW, verbose=False, device=0)[0]
        boxes = r.boxes.xyxy.cpu().numpy() if len(r.boxes) else []
        confs = r.boxes.conf.cpu().numpy() if len(r.boxes) else []
        disp = draw(img, boxes, confs, tag, color)
        # 蓝色虚线框标出 GT（证明目标确实存在）
        for (gx, gy, gw, gh) in gts:
            for i in range(0, gw, 14):
                cv2.line(disp, (gx + i, gy), (gx + min(i + 7, gw), gy), (255, 120, 0), 2)
                cv2.line(disp, (gx + i, gy + gh), (gx + min(i + 7, gw), gy + gh), (255, 120, 0), 2)
            for j in range(0, gh, 14):
                cv2.line(disp, (gx, gy + j), (gx, gy + min(j + 7, gh)), (255, 120, 0), 2)
                cv2.line(disp, (gx + gw, gy + j), (gx + gw, gy + min(j + 7, gh)), (255, 120, 0), 2)
        panels.append(cv2.resize(disp, (1280, 720)))
    out = os.path.join(OUT_DIR, f"compare_{made + 1:02d}.jpg")
    cv2.imwrite(out, np.hstack(panels))
    print(f"[OK] {out}  (min GT area {frac * 100:.3f}% of frame)")
    made += 1

print("DONE")
