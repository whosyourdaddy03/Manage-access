#!/usr/bin/env python3
"""
算法端演示：视频流 → YOLO 检测 → AKF 定位 → 距离/角度/预测轨迹 全叠加
用法（WSL）: ~/yolo/bin/python live_demo.py            # 实时窗口 + 录制
"""
import cv2
import math
import os
import numpy as np
from ultralytics import YOLO
from collections import deque
from akf_demo import AdaptiveKalmanFilter

HEADLESS = not os.environ.get("DISPLAY")  # 无显示环境时只录制不弹窗

VIDEO = "/mnt/d/Graduate/code/demo_video.mp4"
MODEL = "/mnt/d/Graduate/code/runs/p2ema_v8n/weights/best.pt"
REC = "/mnt/d/Graduate/code/demo_recorded.mp4"
CAM_W, CAM_H = 1280, 720

# 距离估计参数（演示用）：fx 按画面宽估算，D = 目标机 Mavic2 对角约 0.35m
FX = CAM_W * 1.2
DRONE_SIZE = 0.35
AKF_ALPHA, AKF_Q = 0.12, 0.008

model = YOLO(MODEL)
cap = cv2.VideoCapture(VIDEO)
vw = cv2.VideoWriter(REC, cv2.VideoWriter_fourcc(*"mp4v"), 30, (CAM_W, CAM_H))

akf = AdaptiveKalmanFilter(alpha=AKF_ALPHA, q_scale=AKF_Q)
trail = deque(maxlen=45)       # EMA 平滑后的中心轨迹（绿色）
raw_pts = deque(maxlen=45)     # 原始检测中心（红色小点，展示抖动）
last_center = None
last_box = None                # (x1,y1,x2,y2) 丢失时画预测框用
last_z = None
miss = 0                       # 连续丢失帧数
frame_i = 0
z_pred_s = None                # 预测距离显示平滑值
FPS = 30.0
JUMP_GATE = 140               # 目标锁定：中心跳变门限(px)
Z_GATE = 1.4                  # 距离门限：突增/突减超过 40% 视为异常量测
COAST_MAX = 30                # 丢失后滤波外推维持跟踪的最长帧数（1秒）
CTR_EMA = 0.35                # 中心 EMA 平滑系数（轨迹用）
PRED_EMA = 0.25               # 预测距离显示平滑

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame_i += 1
    dt = 1.0 / FPS
    disp = frame.copy()

    res = model.predict(frame, imgsz=640, conf=0.3, verbose=False)[0]
    picked = None
    if res.boxes is not None and len(res.boxes):
        xy = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()
        if last_center is None:
            k = int(confs.argmax())                    # 首帧/重锁：最高置信度
            if confs[k] > 0.45:
                picked = k
        else:
            d = np.hypot((xy[:, 0] + xy[:, 2]) / 2 - last_center[0],
                         (xy[:, 1] + xy[:, 3]) / 2 - last_center[1])
            k = int(d.argmin())                        # 之后：锁定最近的目标
            if d[k] < JUMP_GATE:
                picked = k
    if picked is not None:
        x1, y1, x2, y2 = map(int, xy[picked])
        conf = float(confs[picked])
        w_box = max(x2 - x1, 1)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        last_center = (cx, cy)
        last_box = (x1, y1, x2, y2)
        miss = 0

        # --- 定位：距离 + 角度（带异常量测门限）---
        z_raw = FX * DRONE_SIZE / w_box
        akf.predict(dt)
        if last_z is None or (1 / Z_GATE) < (z_raw / last_z) < Z_GATE:
            akf.update(np.array([z_raw], dtype=np.float32))
            last_z = z_raw
        z_akf = float(akf.x[0])
        v_z = float(akf.x[1]) if len(akf.x) > 1 else 0.0
        z_pred = z_akf + v_z * 1.0                # 未来 1s 距离预测
        z_pred = max(z_akf * 0.6, min(z_akf * 1.6, z_pred))   # 显示限幅
        z_pred_s = z_pred if z_pred_s is None else \
            PRED_EMA * z_pred + (1 - PRED_EMA) * z_pred_s
        azim = math.degrees(math.atan((cx - CAM_W / 2) / FX))
        elev = math.degrees(math.atan((cy - CAM_H / 2) / FX))

        # 中心 EMA 平滑后再入轨迹（抑制空对空相机抖动）
        sm = (int(CTR_EMA * cx + (1 - CTR_EMA) * (trail[-1][0] if trail else cx)),
              int(CTR_EMA * cy + (1 - CTR_EMA) * (trail[-1][1] if trail else cy)))
        trail.append(sm)
        raw_pts.append((cx, cy))
        cv2.rectangle(disp, (x1, y1), (x2, y2), (255, 160, 0), 2)
        cv2.putText(disp, f"UAV {conf:.2f}", (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
        # 预测箭头：中心 + 速度方向（限幅防飞出画面）
        pvx = max(-70, min(70, v_z * 50))
        cv2.arrowedLine(disp, sm, (int(sm[0] + pvx), int(sm[1] + pvx * 0.4)),
                        (0, 0, 255), 3, tipLength=0.25)

        panel = [
            f"RAW  dist : {z_raw:6.2f} m",
            f"AKF  dist : {z_akf:6.2f} m",
            f"PRED 1s   : {z_pred_s:6.2f} m",
            f"Azimuth   : {azim:6.1f} deg",
            f"Elevation : {elev:6.1f} deg",
        ]
        for j, s in enumerate(panel):
            color = (0, 255, 255) if j == 2 else (0, 255, 0)
            cv2.putText(disp, s, (14, 34 + j * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
    else:
        miss += 1
        if last_box is not None and miss <= COAST_MAX:
            # 检测丢失：AKF 外推维持跟踪（画黄色预测框）—— 滤波器价值点
            akf.predict(dt)
            x1, y1, x2, y2 = last_box
            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(disp, "PREDICT (coast)", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            z_akf = float(akf.x[0])
            v_z = float(akf.x[1]) if len(akf.x) > 1 else 0.0
            z_pred_c = max(z_akf * 0.6, min(z_akf * 1.6, z_akf + v_z))
            cv2.putText(disp, f"AKF dist : {z_akf:6.2f} m", (14, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 255), 2)
            cv2.putText(disp, f"PRED 1s  : {z_pred_c:6.2f} m", (14, 64),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 255), 2)
        else:
            last_center = None
            last_box = None
            last_z = None
            trail.clear()
            cv2.putText(disp, "searching target ...", (14, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # 原始中心（红点） vs 平滑轨迹（绿线）—— AKF/EMA 平滑效果的直观证据
    for p in raw_pts:
        cv2.circle(disp, p, 2, (0, 0, 255), -1)
    for a, b in zip(list(trail)[:-1], list(trail)[1:]):
        cv2.line(disp, a, b, (0, 255, 0), 2)
    cv2.putText(disp, "raw (red) vs smoothed (green)", (14, CAM_H - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    cv2.putText(disp, f"YOLO+AKF  frame {frame_i}", (CAM_W - 260, CAM_H - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    vw.write(disp)
    if not HEADLESS:
        cv2.imshow("UAV Detection & AKF Localization (algorithm end)", disp)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
vw.release()
cv2.destroyAllWindows()
print(f"录制完成: {REC}")
