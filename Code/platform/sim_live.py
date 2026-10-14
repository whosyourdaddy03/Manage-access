#!/usr/bin/env python3
"""
仿真闭环算法端: TCP帧流(14590) → YOLO检测 → AKF定位 → 测距/角度/预测
                + 真值UDP(14680)对齐 + CSV记录(E-sim评估) + UDP/JSON输出
用法(WSL): ~/yolo/bin/python /mnt/d/Graduate/code/sim_live.py
停止: 窗口按 q
"""
import cv2
import json
import math
import os
import signal
import socket
import threading
import time

import numpy as np
from ultralytics import YOLO

from akf_demo import AdaptiveKalmanFilter

# ---------- 通道配置（与 jMAVSim 改造版对应） ----------
FRAME_HOST, FRAME_PORT = "127.0.0.1", 14590     # TCP 帧流
TRUTH_BIND_PORT = 14680                          # UDP 真值(广播到本机)
JSON_OUT_PORT = 14690                            # UDP/JSON 输出(供QGC桥接/演示)

# ---------- 模型与相机 ----------
MODEL = os.environ.get("SIM_MODEL", "/mnt/d/Graduate/code/runs/p2ema_v8n/weights/best.pt")
CAM_W, CAM_H = 1280, 720
CAM_FOV = math.pi / 3                            # 与 Simulator.java 中 setFieldOfView 一致
FX = (CAM_W / 2) / math.tan(CAM_FOV / 2)         # 1108.5 px, 仿真域精确标定
# 护航相机固定机位(Simulator.java: setViewerPosition(0,-40,-12), 注视(0,-2,-10))
CAM_POS = np.array([0.0, -40.0, -12.0])
# 目标机 3dr_arducopter_quad_x 模型等效直径(m), 经真值标定(z_true/z_raw 中位比 0.973)
DRONE_SIZE = float(os.environ.get("SIM_DRONE_SIZE", "0.255"))

# ---------- AKF 参数(与 live_demo 一致) ----------
AKF_ALPHA, AKF_Q = 0.12, 0.008
JUMP_GATE = 140
Z_GATE = 1.4
COAST_MAX = 15                 # 丢失外推上限(0.5s), 防长外推发散
REJECT_RESET = 5               # 连续拒绝次数上限, 超过强制重置滤波器
CTR_EMA = 0.35

CSV_PATH = os.environ.get("SIM_CSV", "/mnt/d/Graduate/code/report_materials/sim_closed_loop.csv")
REC_PATH = os.environ.get("SIM_REC_PATH", "/mnt/d/Graduate/code/sim_recorded.mp4")

# ---------- 共享状态 ----------
latest_frame = None                              # (ts_ms, jpeg_bytes)
latest_truth = None                              # dict
lock = threading.Lock()
running = True
stop_req = False   # SIGTERM 优雅退出标志(保证录像 moov atom 写入)


def frame_receiver():
    """TCP 收帧线程: 丢旧保新, 只留最新一帧."""
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
                # 尝试解出完整帧: FRAME <ts> <w> <h> <len>\n + jpeg
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
    """UDP 真值线程: t=ms tp=x,y,z tv=vx,vy,vz ep=x,y,z"""
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
            ep = np.array([float(v) for v in f["ep"].split(",")])
            with lock:
                latest_truth = {"t": int(f["t"]), "tp": tp, "tv": tv, "ep": ep}
        except socket.timeout:
            continue
        except Exception:
            continue


def main():
    global running
    model = YOLO(MODEL)
    threading.Thread(target=frame_receiver, daemon=True).start()
    threading.Thread(target=truth_receiver, daemon=True).start()

    js = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # JSON 输出
    NO_REC = os.environ.get("SIM_REC", "1") == "0"          # SIM_REC=0 不录像
    vw = None                                               # 首帧后再建
    csv = open(CSV_PATH, "w", buffering=1)   # 行缓冲, 防中断丢数据
    csv.write("frame,ts_ms,det,conf,x1,y1,x2,y2,z_raw,z_akf,z_pred1s,"
              "azim_deg,elev_deg,z_true_m,err_m,truth_x,truth_y,truth_z\n")

    akf = AdaptiveKalmanFilter(alpha=AKF_ALPHA, q_scale=AKF_Q)
    # 量测噪声初值匹配传感器特性: x,y像素级(亚cm), z高度测距约0.5m标准差
    akf.R = np.diag(np.array([1e-4, 1e-4, 0.25], dtype=np.float64))
    reject_n = 0
    trail, raw_pts = [], []
    last_center, last_box, last_z = None, None, None
    miss, frame_i, fps_meas = 0, 0, 0.0
    t_last = time.time()
    z_pred_s = None
    HEADLESS = not os.environ.get("DISPLAY")

    def _on_term(sig, frm):
        global stop_req
        stop_req = True
    signal.signal(signal.SIGTERM, _on_term)   # timeout/kill 优雅收尾

    print(f"[sim_live] fx={FX:.1f}px drone_size={DRONE_SIZE}m "
          f"csv={CSV_PATH}  等待帧流...")
    while not stop_req:
        with lock:
            fr = latest_frame
        if fr is None:
            time.sleep(0.05)
            continue
        ts_ms, jpeg = fr
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        frame_i += 1
        now = time.time()
        fps_meas = 0.9 * fps_meas + 0.1 / max(now - t_last, 1e-6)
        t_last = now
        dt = 1.0 / 30.0
        with lock:
            truth = dict(latest_truth) if latest_truth else None
        disp = frame.copy()
        if vw is None and not NO_REC:
            vw = cv2.VideoWriter(REC_PATH, cv2.VideoWriter_fourcc(*"mp4v"),
                                 30, (frame.shape[1], frame.shape[0]))

        # --- 检测 + 锁定(仿真域conf整体偏低, 阈值取0.25平衡质量与检出率) ---
        res = model.predict(frame, imgsz=640, conf=0.25, verbose=False)[0]
        picked = None
        confs = np.array([])
        conf_best = 0.0
        if res.boxes is not None and len(res.boxes):
            xy = res.boxes.xyxy.cpu().numpy()
            confs = res.boxes.conf.cpu().numpy()
            conf_best = float(confs.max())   # 先验过滤前原始最高置信度(全帧检出率口径)
            # 量测距离先验(目标活动空域3~12m): 剔除ego机/远景树枝伪影, 防锁污染
            zc = FX * DRONE_SIZE / np.maximum(xy[:, 3] - xy[:, 1], 1)
            ok = (zc > 3.0) & (zc < 12.0)
            xy, confs = xy[ok], confs[ok]
        if picked is None and len(confs):
            if last_center is None:
                k = int(confs.argmax())
                if confs[k] > 0.55:      # 高门限初锁, 防止锁定背景伪影
                    picked = k
            else:
                d = np.hypot((xy[:, 0] + xy[:, 2]) / 2 - last_center[0],
                             (xy[:, 1] + xy[:, 3]) / 2 - last_center[1])
                k = int(d.argmin())
                if d[k] < JUMP_GATE:
                    picked = k

        z_true = err = None
        if truth is not None:
            z_true = float(np.linalg.norm(truth["tp"] - CAM_POS))

        det, conf_v = 0, 0.0
        if picked is not None:
            x1, y1, x2, y2 = map(int, xy[picked])
            conf_v = float(confs[picked])
            det = 1
            w_box = max(x2 - x1, 1)
            h_box = max(y2 - y1, 1)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            last_center, last_box, miss = (cx, cy), (x1, y1, x2, y2), 0

            z_raw = FX * DRONE_SIZE / h_box   # 高度测距: 对yaw旋转稳健
            # --- AKF: 6维状态[x,y,z,vx,vy,vz] + Sage-Husa自适应R ---
            # 单目量测反投影为相机系3D位置 (x右, y下, z前)
            meas = np.array([(cx - CAM_W / 2) / FX * z_raw,
                             (cy - CAM_H / 2) / FX * z_raw,
                             z_raw], dtype=np.float32)
            akf.predict(dt)
            accepted = last_z is None or \
                (1 / Z_GATE) < (z_raw / last_z) < Z_GATE
            if accepted:
                akf.update(meas)
                last_z = z_raw
                reject_n = 0
            else:
                reject_n += 1
                if reject_n >= REJECT_RESET and conf_v >= 0.5:
                    # 持续高置信但距离门限拒绝: 量测源真实跳变(目标快速机动),
                    # 强制重置滤波器重新收敛
                    akf = AdaptiveKalmanFilter(alpha=AKF_ALPHA, q_scale=AKF_Q)
                    last_z = None
                    reject_n = 0
                    akf.predict(dt)
                    akf.update(meas)
                    last_z = z_raw
                elif reject_n >= REJECT_RESET * 3:
                    # 持续低质量量测: 疑似锁定到伪影, 放弃跟踪重新搜索
                    last_center = last_box = last_z = None
                    reject_n = 0
                    trail.clear()
                    raw_pts.clear()
            z_akf = float(akf.x[2])            # 相机系z = 距离
            v_z = float(akf.x[5])              # 距离变化率
            pos_pred = akf.predict_future(1.0)
            z_pred = max(z_akf * 0.6, min(z_akf * 1.6, float(pos_pred[2])))
            z_pred_s = z_pred if z_pred_s is None else \
                0.25 * z_pred + 0.75 * z_pred_s
            # 方位/俯仰角像素直算: atan((c-c0)/f), 不经过AKF横向状态
            # (coast外推无漂移风险; 护航相机自动注视目标, 真值视轴偏角≈0)
            azim = math.degrees(math.atan((cx - CAM_W / 2) / FX))
            elev = math.degrees(math.atan((cy - CAM_H / 2) / FX))
            if z_true is not None:
                err = z_akf - z_true

            sm = (int(CTR_EMA * cx + (1 - CTR_EMA) * (trail[-1][0] if trail else cx)),
                  int(CTR_EMA * cy + (1 - CTR_EMA) * (trail[-1][1] if trail else cy)))
            trail.append(sm)
            raw_pts.append((cx, cy))
            cv2.rectangle(disp, (x1, y1), (x2, y2), (255, 160, 0), 2)
            cv2.putText(disp, f"UAV {conf_v:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
            pvx = max(-70, min(70, v_z * 50))
            cv2.arrowedLine(disp, sm, (int(sm[0] + pvx), int(sm[1] + pvx * 0.4)),
                            (0, 0, 255), 3, tipLength=0.25)

            panel = [
                f"RAW  dist : {z_raw:6.2f} m",
                f"AKF  dist : {z_akf:6.2f} m" +
                (f"   err {err:+.2f}" if err is not None else ""),
                f"PRED 1s   : {z_pred_s:6.2f} m",
                f"Azimuth   : {azim:6.1f} deg",
                f"Truth     : {z_true:6.2f} m" if z_true is not None else "Truth     : waiting",
            ]
            for j, s_ in enumerate(panel):
                color = (0, 255, 255) if j in (2, 4) else (0, 255, 0)
                cv2.putText(disp, s_, (14, 34 + j * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)

            tx = truth["tp"] if truth else [0, 0, 0]
            csv.write(f"{frame_i},{ts_ms},{det},{conf_v:.3f},{x1},{y1},{x2},{y2},"
                      f"{z_raw:.3f},{z_akf:.3f},{z_pred_s:.3f},{azim:.2f},{elev:.2f},"
                      f"{z_true if z_true is not None else -1:.3f},"
                      f"{err if err is not None else 0:.3f},"
                      f"{tx[0]:.2f},{tx[1]:.2f},{tx[2]:.2f}\n")

            # UDP/JSON 输出(QGC桥接约定)
            payload = {
                "src": "sim", "ts": ts_ms, "conf": round(conf_v, 3),
                "dist_m": round(z_akf, 2), "dist_raw": round(z_raw, 2),
                "dist_pred1s": round(z_pred_s or 0, 2),
                "azimuth_deg": round(azim, 1), "elevation_deg": round(elev, 1),
                "box": [x1, y1, x2, y2],
                "truth_dist": round(z_true, 2) if z_true else None,
            }
            js.sendto(json.dumps(payload).encode(),
                      ("127.0.0.1", JSON_OUT_PORT))
        else:
            miss += 1
            if last_box is not None and miss <= COAST_MAX:
                akf.predict(dt)
                x1, y1, x2, y2 = last_box
                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(disp, "PREDICT (coast)", (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                z_akf = float(akf.x[2])   # coast帧记录前向距离(修复: 原误写横向状态x[0])
                csv.write(f"{frame_i},{ts_ms},0,0,0,0,0,0,0,{z_akf:.3f},0,0,0,"
                          f"{z_true if z_true is not None else -1:.3f},0,0,0,0\n")
            else:
                last_center = last_box = last_z = None
                trail.clear()
                raw_pts.clear()
                cv2.putText(disp, "searching target ...", (14, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                # 全帧记录(搜索帧): 真实检出率口径, conf=先验过滤前最高置信度
                tx = truth["tp"] if truth else [0.0, 0.0, 0.0]
                zt_row = z_true if z_true is not None else -1.0
                csv.write(f"{frame_i},{ts_ms},0,{conf_best:.3f},0,0,0,0,0,0,0,0,0,"
                          f"{zt_row:.3f},0,{tx[0]:.2f},{tx[1]:.2f},{tx[2]:.2f}\n")

        for p in raw_pts:
            cv2.circle(disp, p, 2, (0, 0, 255), -1)
        for a, b in zip(raw_pts[:-1], raw_pts[1:]):
            cv2.line(disp, a, b, (0, 255, 0), 2)
        cv2.putText(disp, f"sim closed-loop  {fps_meas:4.1f} fps  frame {frame_i}",
                    (CAM_W - 340, CAM_H - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        if vw is not None:
            vw.write(disp)
        if not HEADLESS:
            cv2.imshow("SIM closed-loop: detect+AKF+truth", disp)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        elif frame_i % 150 == 0:
            print(f"[sim_live] frame {frame_i}  {fps_meas:.1f} fps")

    running = False
    if vw:
        vw.release()
    csv.close()
    cv2.destroyAllWindows()
    print(f"结束: {frame_i} 帧, CSV={CSV_PATH}, 录像={REC_PATH}")


if __name__ == "__main__":
    main()
