#!/usr/bin/env python3
"""
platform_detector: PySide6 无人机检测管线封装
  - 复用 gen_result_video.py v2 的所有改进: conf≥0.20 + 退化过滤 + AKF平滑轨迹 + 方向安全预测
  - 复用 akf_demo.py 的 AdaptiveKalmanFilter
  - 输出 dict 数据给 UI 使用
"""
import math
import os
import threading
import time
from collections import deque

import cv2
import numpy as np

from akf_demo import AdaptiveKalmanFilter

# ---------- 配置 ----------
BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE, "runs", "detect", "p2ema_simft", "weights", "best.pt")
CONF_THRESHOLD = 0.20       # 维持跟踪门限(参数页可调): 低于此值不进入候选
DRONE_SIZE = 0.270          # finetune 后等效尺寸
MA_WINDOW = 10              # 修复3: 滑动窗口长度
TRAJ_LEN = 60               # 轨迹点数上限

# ---------- 搜索/锁定状态机参数(迁移自 sim_live.py, 已在闭环仿真验证) ----------
LOCK_INIT_CONF = 0.55       # 初锁高门限: 防背景伪影误锁定
JUMP_GATE = 140.0           # 维持跟踪: 候选框中心与上一目标的像素距离门限
Z_GATE = 1.4                # 相邻帧测距突变门限(倍): 超出判为异常量测
REJECT_RESET = 5            # 连续拒绝≥5帧且高置信 → 目标真实机动, 重置滤波器
REJECT_DROP = 15            # 连续拒绝≥15帧 → 疑似锁到伪影, 放弃跟踪回搜索
COAST_SEC = 1.0             # 丢帧外推预算(秒): 超时回 SEARCH, 防长外推发散


class DroneDetector:
    """检测管线封装: YOLO → 退化过滤 → AKF → 测距/角度/预测 → 叠加帧"""

    def __init__(self, model_path=None):
        # 懒加载: 模型(含GPU/cuDNN初始化)移到首次 detect() 的工作线程内,
        # 避免主窗口构造时同步加载十几秒导致界面"卡死无窗口"
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self._model_lock = threading.Lock()
        self._ready = threading.Event()   # 加载+哑推理预热全部完成才置位
        self.akf = AdaptiveKalmanFilter(alpha=0.12, q_scale=0.008)
        self.pos_history = deque(maxlen=MA_WINDOW)
        self.trajectory = deque(maxlen=TRAJ_LEN)
        self.fx = None  # 首次检测后设
        self.cx = None
        self.cy = None
        self.dt = 1.0 / 30.0
        self.total_frames = 0
        self.det_frames = 0
        # 可动态调整的参数
        self.conf_threshold = CONF_THRESHOLD
        self.drone_size = DRONE_SIZE
        # ---- 搜索/锁定状态机 ----
        self.state = "SEARCH"          # SEARCH / LOCKED / COAST
        self.last_center = None        # 上一帧目标像素中心 (cx, cy)
        self.last_box = None           # 上一帧框 (x1,y1,x2,y2)
        self.last_z = None             # 上一帧被接受的测距(m)
        self.last_conf = 0.0           # 最近一次真实检测置信度(coast显示用)
        self.reject_n = 0              # Z_GATE 连续拒绝计数
        self.miss_sec = 0.0            # 累计丢帧时间(秒)
        self._t_prev = None            # 帧间隔计时

    def _new_akf(self):
        return AdaptiveKalmanFilter(alpha=0.12, q_scale=0.008)

    def _reset_track(self):
        """放弃当前航迹, 回到搜索状态。"""
        self.state = "SEARCH"
        self.last_center = None
        self.last_box = None
        self.last_z = None
        self.last_conf = 0.0
        self.reject_n = 0
        self.miss_sec = 0.0
        self.akf = self._new_akf()
        self.pos_history.clear()
        self.trajectory.clear()

    def set_conf_threshold(self, v):
        self.conf_threshold = float(v)

    def set_drone_size(self, v):
        self.drone_size = float(v)

    def reset_stats(self):
        """开始新一轮检测时清空滤波/状态机/计数(不重新加载模型)。"""
        self.akf = self._new_akf()
        self.pos_history = deque(maxlen=MA_WINDOW)
        self.trajectory = deque(maxlen=TRAJ_LEN)
        self.fx = self.cx = self.cy = None
        self.total_frames = 0
        self.det_frames = 0
        self.state = "SEARCH"
        self.last_center = None
        self.last_box = None
        self.last_z = None
        self.last_conf = 0.0
        self.reject_n = 0
        self.miss_sec = 0.0
        self._t_prev = None

    def load_model(self):
        """显式加载模型(幂等, 线程安全)并做一次哑推理预热。
        在程序启动后的后台线程调用, 使首次真实检测不再等待
        模型加载 + CUDA/cuDNN 首次推理初始化(合计可达十几秒)。
        预热在途时另一线程调用本方法会阻塞到预热完成。"""
        if self._ready.is_set():
            return
        with self._model_lock:
            if self.model is None:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                # 哑推理: 触发 fuse/cuDNN 内核选择/GPU 上下文初始化
                import numpy as _np
                _dummy = _np.zeros((640, 640, 3), _np.uint8)
                self.model(_dummy, verbose=False)
            self._ready.set()

    def _set_camera(self, frame):
        h, w = frame.shape[:2]
        self.fx = (w / 2) / math.tan(math.pi / 6)  # 60° FOV
        self.cx, self.cy = w / 2, h / 2

    def detect(self, frame):
        """处理单帧, 返回 (叠加帧, 数据dict)。

        状态机(迁移自 sim_live.py 闭环验证版本):
          SEARCH: 无航迹, 取全帧置信度最高候选, 须 conf > 0.55 才初锁;
          LOCKED: 取距上一目标中心最近的候选, 像素跳变 < 140 才采用,
                  测距突变超 1.4 倍的量测被 Z_GATE 拒绝(连续拒绝触发
                  滤波器重置或放弃航迹);
          COAST : 丢帧后仅做 AKF 外推, 预算 0.6s, 超时回 SEARCH。
        """
        # 幂等: 未加载则在此(工作线程内)加载; 后台预热在途则等其完成
        self.load_model()
        if self.fx is None:
            self._set_camera(frame)

        self.total_frames += 1
        overlay = frame.copy()

        # 帧间隔(用于 coast 时间预算; AKF 仍用固定 1/30s, 与验证版一致)
        now = time.time()
        if self._t_prev is not None:
            dt_wall = min(max(now - self._t_prev, 0.001), 0.5)
        else:
            dt_wall = self.dt
        self._t_prev = now

        # 1. YOLO 推理 + 先验候选过滤
        res = self.model(frame, conf=0.10, verbose=False)
        boxes = res[0].boxes
        candidates = []          # (conf, x1,y1,x2,y2, bw,bh, z_i)
        if len(boxes) > 0:
            confs = boxes.conf.cpu().numpy()
            xyxys = boxes.xyxy.cpu().numpy()
            for idx in range(len(boxes)):
                c = float(confs[idx])
                if c < self.conf_threshold:
                    continue
                x1, y1, x2, y2 = xyxys[idx].tolist()
                bw, bh = x2 - x1, y2 - y1
                if bh < 8 or bh > 200:
                    continue
                ar = bw / max(bh, 1)
                if ar > 5.0 or ar < 0.2:
                    continue
                z_i = self.drone_size * self.fx / max(bh, 1)
                if z_i < 3 or z_i > 30:
                    continue
                candidates.append((c, x1, y1, x2, y2, bw, bh, z_i))

        # 2. 状态机选框
        picked = None
        if candidates:
            if self.last_center is None:
                # SEARCH → 高门限初锁, 防背景伪影
                k = max(range(len(candidates)), key=lambda i: candidates[i][0])
                if candidates[k][0] > LOCK_INIT_CONF:
                    picked = candidates[k]
            else:
                # LOCKED/COAST → 最近邻 + 跳变门限, 防目标切换/框跳
                dxs = [math.hypot((c[1] + c[3]) / 2 - self.last_center[0],
                                  (c[2] + c[4]) / 2 - self.last_center[1])
                       for c in candidates]
                k = min(range(len(candidates)), key=lambda i: dxs[i])
                if dxs[k] < JUMP_GATE:
                    picked = candidates[k]

        data = {
            "det": False, "tracked": False, "conf": 0.0,
            "x1": 0, "y1": 0, "x2": 0, "y2": 0,
            "box_w": 0, "box_h": 0,
            "z_raw": 0.0, "z_akf": 0.0, "z_pred": 0.0,
            "azim": 0.0, "elev": 0.0,
            "fps": 0.0, "status": "SEARCHING",
            "akf_cx": 0, "akf_cy": 0, "pred_cx": 0, "pred_cy": 0,
            "draw_pred": False, "traj_pts": [],
        }

        if picked is not None and self._handle_pick(picked, data, dt_wall):
            # LOCKED: 量测被接受(或重置后接受), 正常叠加
            self.state = "LOCKED"
            self._draw_overlay(overlay, data)
        elif self.last_box is not None and self.miss_sec + dt_wall <= COAST_SEC + 1e-6:
            # COAST: 无有效量测且本帧仍在 0.6s 外推预算内
            self._handle_coast(data, dt_wall)
            self.state = "COAST"
            self._draw_coast(overlay, data)
        else:
            # SEARCH: 无航迹或外推超时
            self._reset_track()
            data["status"] = "SEARCHING"
            self._draw_search(overlay, data)

        return overlay, data

    # ---------- 状态机: 有量测 ----------
    def _handle_pick(self, picked, data, dt_wall):
        """处理选中候选。返回 True 表示本帧 LOCKED; False 表示量测被
        Z_GATE 连续拒绝到放弃航迹(应转 coast/search)。"""
        conf_val, x1, y1, x2, y2, bw, bh, z_raw = picked
        cx_box, cy_box = (x1 + x2) / 2, (y1 + y2) / 2
        azim = math.degrees(math.atan2(cx_box - self.cx, self.fx))
        elev = math.degrees(math.atan2(cy_box - self.cy, self.fx))

        z3d = max(z_raw, 0.1)
        x3d = z3d * math.tan(math.radians(azim))
        y3d = -z3d * math.tan(math.radians(elev))
        meas = np.array([x3d, y3d, z3d])

        self.akf.predict(self.dt)
        accepted = self.last_z is None or \
            (1.0 / Z_GATE) < (z_raw / self.last_z) < Z_GATE

        if not accepted:
            self.reject_n += 1
            if self.reject_n >= REJECT_DROP:
                # 持续低质量量测: 疑似锁定伪影, 放弃航迹重新搜索
                self._reset_track()
                return False
            if self.reject_n >= REJECT_RESET and conf_val >= 0.5:
                # 持续高置信但距离门限拒绝: 目标真实机动, 重置滤波器重收敛
                self.akf = self._new_akf()
                self.last_z = None
                self.reject_n = 0
                self.akf.predict(self.dt)
                self.akf.update(meas)
                self.last_z = z_raw
            # 其余拒绝帧: 不更新滤波器, 沿用预测, 仍按 LOCKED 显示
        else:
            self.akf.update(meas)
            self.last_z = z_raw
            self.reject_n = 0

        self.det_frames += 1
        self.last_center = (cx_box, cy_box)
        self.last_box = (int(x1), int(y1), int(x2), int(y2))
        self.last_conf = conf_val
        self.miss_sec = 0.0

        akf_pos = self.akf.x[:3].copy()
        akf_vel = self.akf.x[3:].copy()
        akf_dist = float(np.linalg.norm(akf_pos))
        self.pos_history.append((self.total_frames, akf_pos.copy()))

        akf_cx = self.cx + akf_pos[0] / max(akf_pos[2], 0.1) * self.fx
        akf_cy = self.cy - akf_pos[1] / max(akf_pos[2], 0.1) * self.fx
        self.trajectory.append((akf_cx, akf_cy))

        # 1s 预测方向: 滑动窗口拟合速度 + 方向安全检查
        draw_pred, pred_dist = False, 0.0
        pred_cx, pred_cy = 0, 0
        if len(self.pos_history) >= 5:
            times = np.array([t for t, _ in self.pos_history])
            positions = np.array([p for _, p in self.pos_history])
            dt_vec = times - times.mean()
            vel_fit = np.array([
                np.dot(dt_vec, positions[:, i]) / np.dot(dt_vec, dt_vec)
                for i in range(3)])
            akf_speed = np.linalg.norm(akf_vel)
            fit_speed = np.linalg.norm(vel_fit)
            if akf_speed > 0.01 and fit_speed > 0.01:
                cos_sim = np.dot(akf_vel, vel_fit) / (akf_speed * fit_speed)
                if cos_sim > -0.3:
                    pred_pos = akf_pos + vel_fit * 1.0
                    pred_dist = float(np.linalg.norm(pred_pos))
                    pred_cx = self.cx + pred_pos[0] / max(pred_pos[2], 0.1) * self.fx
                    pred_cy = self.cy - pred_pos[1] / max(pred_pos[2], 0.1) * self.fx
                    draw_pred = True
            else:
                pred_pos = akf_pos + akf_vel * 1.0
                pred_dist = float(np.linalg.norm(pred_pos))
                pred_cx = self.cx + pred_pos[0] / max(pred_pos[2], 0.1) * self.fx
                pred_cy = self.cy - pred_pos[1] / max(pred_pos[2], 0.1) * self.fx
                draw_pred = True

        data.update({
            "det": True, "tracked": True, "conf": conf_val,
            "x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2),
            "box_w": bw, "box_h": bh,
            "z_raw": z_raw, "z_akf": akf_dist, "z_pred": pred_dist,
            "azim": azim, "elev": elev,
            "status": "LOCKED",
            "akf_cx": int(akf_cx), "akf_cy": int(akf_cy),
            "pred_cx": int(pred_cx), "pred_cy": int(pred_cy),
            "draw_pred": draw_pred,
            "traj_pts": [(int(x), int(y)) for x, y in self.trajectory],
        })
        return True

    # ---------- 状态机: 丢帧外推 ----------
    def _handle_coast(self, data, dt_wall):
        self.miss_sec += dt_wall
        self.akf.predict(self.dt)
        akf_pos = self.akf.x[:3].copy()
        akf_dist = float(np.linalg.norm(akf_pos))
        # 由 AKF 外推位置反算方位/俯仰, 供地图/仪表短时延续
        azim = math.degrees(math.atan2(akf_pos[0], max(akf_pos[2], 0.1)))
        elev = -math.degrees(math.atan2(akf_pos[1], max(akf_pos[2], 0.1)))
        akf_cx = self.cx + akf_pos[0] / max(akf_pos[2], 0.1) * self.fx
        akf_cy = self.cy - akf_pos[1] / max(akf_pos[2], 0.1) * self.fx
        x1, y1, x2, y2 = self.last_box
        data.update({
            "det": False, "tracked": True, "conf": self.last_conf,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "box_w": x2 - x1, "box_h": y2 - y1,
            "z_raw": 0.0, "z_akf": akf_dist,
            "azim": azim, "elev": elev,
            "status": "COAST",
            "akf_cx": int(akf_cx), "akf_cy": int(akf_cy),
            "traj_pts": [(int(x), int(y)) for x, y in self.trajectory],
        })

    def _draw_overlay(self, frame, d):
        GREEN = (0, 255, 0)
        YELLOW = (0, 255, 255)
        BLUE = (255, 100, 0)
        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)

        # 检测框
        cv2.rectangle(frame, (d["x1"], d["y1"]), (d["x2"], d["y2"]), GREEN, 2)
        cv2.putText(frame, f"drone {d['conf']:.2f}", (d["x1"], d["y1"] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2)

        # AKF 平滑中心十字
        cv2.drawMarker(frame, (d["akf_cx"], d["akf_cy"]), YELLOW, cv2.MARKER_CROSS, 20, 2)

        # 轨迹
        traj = d["traj_pts"]
        if len(traj) >= 2:
            for i in range(1, len(traj)):
                cv2.line(frame, traj[i - 1], traj[i], BLUE, 2)

        # 预测点 (方向安全才画)
        if d["draw_pred"]:
            cv2.drawMarker(frame, (d["pred_cx"], d["pred_cy"]), YELLOW, cv2.MARKER_DIAMOND, 25, 2)
            cv2.putText(frame, "1s pred", (d["pred_cx"] + 15, d["pred_cy"]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, YELLOW, 1)

        # 数据面板
        panel = [
            f"RAW dist:   {d['z_raw']:.1f} m",
            f"AKF dist:   {d['z_akf']:.1f} m",
            f"1s pred:    {d['z_pred']:.1f} m",
            f"Azimuth:    {d['azim']:.2f} deg",
            f"Elevation:  {d['elev']:.2f} deg",
            f"Confidence: {d['conf']:.2f}",
            f"Status: LOCKED",
        ]
        self._draw_panel(frame, panel)

    def _draw_coast(self, frame, d):
        YELLOW = (0, 255, 255)
        # 上一帧检测框(黄色, 表示外推维持)
        cv2.rectangle(frame, (d["x1"], d["y1"]), (d["x2"], d["y2"]), YELLOW, 2)
        cv2.putText(frame, "PREDICT (coast)", (d["x1"], d["y1"] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, YELLOW, 2)
        # AKF 外推中心十字
        cv2.drawMarker(frame, (d["akf_cx"], d["akf_cy"]), YELLOW,
                       cv2.MARKER_CROSS, 20, 2)
        # 轨迹保留
        traj = d["traj_pts"]
        if len(traj) >= 2:
            for i in range(1, len(traj)):
                cv2.line(frame, traj[i - 1], traj[i], (255, 100, 0), 2)
        panel = [
            f"RAW dist:   -- m",
            f"AKF dist:   {d['z_akf']:.1f} m (coast)",
            f"1s pred:    -- m",
            f"Azimuth:    {d['azim']:.2f} deg",
            f"Elevation:  {d['elev']:.2f} deg",
            f"Confidence: {d['conf']:.2f}",
            f"Status: COAST (extrapolating)",
        ]
        self._draw_panel(frame, panel)

    def _draw_search(self, frame, d):
        RED = (0, 0, 255)
        cv2.putText(frame, "searching target ...", (14, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, RED, 2)
        panel = [
            f"RAW dist:   -- m",
            f"AKF dist:   -- m",
            f"1s pred:    -- m",
            f"Azimuth:    -- deg",
            f"Elevation:  -- deg",
            f"Confidence: --",
            f"Status: SEARCHING",
        ]
        self._draw_panel(frame, panel)

    def _draw_panel(self, frame, lines):
        WHITE = (255, 255, 255)
        h = len(lines) * 28 + 20
        cv2.rectangle(frame, (10, 10), (290, 10 + h), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (290, 10 + h), (50, 50, 50), 1)
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (20, 35 + i * 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1)
