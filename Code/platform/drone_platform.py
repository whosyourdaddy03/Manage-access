#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无人机识别与定位系统 DRLS (PySide6 三页签大屏)
  页签1 目标态势: 左目标列表 + 中卫星地图/视频浮窗 + 右方位距离仪表 + 底部实时数据条
  页签2 检测回放: 历史录像播放 + 时间轴 + CSV 距离曲线联动
  页签3 参数设置: 置信度/等效尺寸/UDP/定位锚点/地图模式
  输入: 视频文件 / 摄像头 / jMAVSim TCP 实时帧流
  输出: 界面显示 / MP4录制 / UDP JSON 14690
"""
import csv
import json
import math
import os
import socket
import sys
import threading
import time

import cv2
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as MplCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPoint
from PySide6.QtGui import (QImage, QPixmap, QFont, QColor, QPainter, QPen,
                            QBrush, QPolygon)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QGridLayout, QLineEdit,
    QComboBox, QStatusBar, QSlider, QCheckBox, QTabWidget,
    QFrame, QDoubleSpinBox, QRadioButton, QGroupBox, QDialog
)

from platform_detector import DroneDetector
from tcp_frame_source import TcpFrameSource
from platform_map import MapView, DEFAULT_ANCHOR
from config_store import load_config, save_config, DEFAULTS as CFG_DEFAULTS

# 逐帧检测记录(CSV)输出目录: 程序目录/records
RECORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records")


# ================= 主题样式 =================
QSS = """
QMainWindow, QWidget { background:#0b1220; color:#dbe7f5;
    font-family:"Microsoft YaHei","SimHei",sans-serif; font-size:13px; }
#Header { background:#101a2c; border-bottom:2px solid #2563eb; }
#Title { color:#7dd3fc; font-size:20px; font-weight:bold; }
#Subtitle { color:#64748b; font-size:11px; letter-spacing:3px; }
QTabWidget::pane { border:1px solid #1e3a55; background:#0b1220; top:-1px; }
QTabBar::tab { background:#101a2c; color:#94a3b8; padding:10px 34px;
    border:1px solid #1e3a55; border-bottom:none; margin-right:2px;
    font-size:14px; font-weight:bold; }
QTabBar::tab:selected { background:#0b1220; color:#38bdf8;
    border-top:2px solid #38bdf8; }
QGroupBox { border:1px solid #1e3a55; border-radius:8px; margin-top:12px;
    padding:14px 10px 10px 10px; font-weight:bold; color:#9fc5ff; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }
QPushButton { background:#17263d; border:1px solid #2b4a73; border-radius:5px;
    padding:7px 16px; color:#dbe7f5; }
QPushButton:hover { background:#1d3354; }
QPushButton:pressed { background:#25477a; }
QPushButton:checked { background:#0f5a3e; border-color:#22c55e; color:#d1fae5; }
#BigBtn { padding:12px; font-size:15px; font-weight:bold; }
#BigBtn:checked { background:#7f1d1d; border-color:#ef4444; color:#fecaca; }
QLabel { color:#c6d6ea; }
#Card { background:#0f1c30; border:1px solid #20415f; border-radius:8px; }
#CardActive { background:#0e2a3a; border:1.5px solid #38bdf8; border-radius:8px; }
#DataStrip { background:#101a2c; border-top:1px solid #1e3a55; }
#DataKey { color:#7c93ad; font-size:11px; }
#DataVal { color:#e6f1ff; font-size:16px; font-weight:bold; }
QStatusBar { background:#0a111d; color:#7c93ad; }
QComboBox, QLineEdit, QDoubleSpinBox { background:#0a111d; border:1px solid #2b4a73;
    border-radius:4px; padding:5px 8px; color:#e6f1ff; }
QSlider::groove:horizontal { height:5px; background:#1e3a55; border-radius:2px; }
QSlider::sub-page:horizontal { background:#2563eb; border-radius:2px; }
QSlider::handle:horizontal { background:#38bdf8; width:15px; height:15px;
    margin:-6px 0; border-radius:7px; }
QCheckBox { color:#c6d6ea; spacing:6px; }
QCheckBox::indicator { width:16px; height:16px; }
QCheckBox::indicator:checked { background:#2563eb; border:1px solid #38bdf8; border-radius:3px; }
"""

# 告警分级颜色(对应样例黄色围栏)
LV_RED, LV_ORANGE, LV_YELLOW, LV_GREEN, LV_GRAY = \
    "red", "orange", "yellow", "green", "gray"
LV_COLOR = {"red": "#ef4444", "orange": "#f97316", "yellow": "#eab308",
             "green": "#22c55e", "gray": "#64748b"}
LV_TEXT = {"red": "危险入侵", "orange": "高威胁", "yellow": "警戒",
           "green": "安全", "gray": "搜索中", "": "--"}


def alarm_level(det, z):
    if not det or z <= 0:
        return LV_GRAY
    if z < 3:
        return LV_RED
    if z < 5:
        return LV_ORANGE
    if z < 8:
        return LV_YELLOW
    return LV_GREEN


# --------- 文件对话框(强制 Qt 自绘, 规避 WSLg 原生 GTK 框卡死) ---------
def pick_open_file(parent, title, file_filter):
    """选择已有文件; 取消返回 ''。"""
    dlg = QFileDialog(parent, title, "", file_filter)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
    if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selectedFiles():
        return dlg.selectedFiles()[0]
    return ""


def pick_save_file(parent, title, file_filter, default_name=""):
    """选择保存路径; 取消返回 ''。"""
    dlg = QFileDialog(parent, title, default_name, file_filter)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selectedFiles():
        return dlg.selectedFiles()[0]
    return ""


# ================= 检测线程(沿用, TCP走适配器) =================
class DetThread(QThread):
    frame_ready = Signal(object)
    data_ready = Signal(dict)
    fps_update = Signal(float)
    rec_state_changed = Signal(bool)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.src_type = "file"
        self.src_path = ""
        self.cap = None
        self._running = False
        self._fps = 0.0
        self._t_last = time.time()
        self._rec = False
        self._rec_writer = None
        self._rec_path = ""
        self._rec_fps = 30.0
        self._udp = False
        self._udp_sock = None
        self._udp_host = "127.0.0.1"
        self._udp_port = 14690
        self._udp_t_last = 0
        # 逐帧 CSV 检测记录
        self._csv_file = None
        self._csv_writer = None
        self._csv_path = ""
        self._csv_rows = 0
        self._csv_src = ""

    CSV_HEADER = [
        "frame", "ts_ms", "status", "det", "tracked", "conf",
        "x1", "y1", "x2", "y2", "box_w", "box_h",
        "z_raw", "z_akf", "z_pred1s", "azim_deg", "elev_deg", "fps", "src",
    ]

    def start_csv(self, path, src_label=""):
        """检测开始时打开逐帧记录文件(行缓冲, 异常中断不丢已写数据)。"""
        self._csv_path, self._csv_src = path, src_label
        self._csv_rows = 0
        self._csv_file = open(path, "w", buffering=1, newline="",
                              encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(self.CSV_HEADER)

    def stop_csv(self):
        if self._csv_file:
            try:
                self._csv_file.close()
            except Exception:
                pass
        self._csv_file = None
        self._csv_writer = None
        return self._csv_path, self._csv_rows

    def set_source(self, src_type, src_path=""):
        self.src_type, self.src_path = src_type, src_path

    def start_recording(self, path, fps=30.0):
        self._rec_path, self._rec_fps, self._rec = path, fps, True
        self._rec_writer = None
        self.rec_state_changed.emit(True)

    def stop_recording(self):
        self._rec = False
        if self._rec_writer:
            self._rec_writer.release()
            self._rec_writer = None
        self.rec_state_changed.emit(False)

    def set_udp(self, enabled, host="127.0.0.1", port=14690):
        self._udp, self._udp_host, self._udp_port = enabled, host, port
        if enabled and not self._udp_sock:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif not enabled and self._udp_sock:
            self._udp_sock.close()
            self._udp_sock = None

    def run(self):
        self._running = True
        if self.src_type == "file":
            self.cap = cv2.VideoCapture(self.src_path)
        elif self.src_type == "camera":
            self.cap = cv2.VideoCapture(0)
        elif self.src_type == "tcp":
            self.cap = TcpFrameSource.from_path(self.src_path)
        else:
            self._running = False
            return
        if not self.cap.isOpened():
            self._running = False
            self.stop_csv()
            self.data_ready.emit({"status": "ERROR", "error": "无法打开视频源"})
            return

        self._t_last, self._udp_t_last = time.time(), 0
        self._t0 = self._t_last
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                if self.src_type == "file":
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                elif self.src_type == "tcp":
                    continue
                else:
                    break
            now = time.time()
            dt = now - self._t_last
            if dt > 0:
                self._fps = 0.9 * self._fps + 0.1 / dt
            self._t_last = now

            overlay, data = self.detector.detect(frame)

            if self._csv_writer is not None:
                self._csv_writer.writerow([
                    self.detector.total_frames,
                    int((now - self._t0) * 1000),
                    data.get("status", ""),
                    int(bool(data.get("det"))),
                    int(bool(data.get("tracked", False))),
                    f"{data.get('conf', 0):.3f}",
                    data.get("x1", 0), data.get("y1", 0),
                    data.get("x2", 0), data.get("y2", 0),
                    f"{data.get('box_w', 0):.1f}", f"{data.get('box_h', 0):.1f}",
                    f"{data.get('z_raw', 0):.3f}", f"{data.get('z_akf', 0):.3f}",
                    f"{data.get('z_pred', 0):.3f}",
                    f"{data.get('azim', 0):.3f}", f"{data.get('elev', 0):.3f}",
                    f"{self._fps:.1f}", self._csv_src,
                ])
                self._csv_rows += 1

            if self._rec:
                h, w = overlay.shape[:2]
                if self._rec_writer is None:
                    self._rec_writer = cv2.VideoWriter(
                        self._rec_path, cv2.VideoWriter_fourcc(*'mp4v'),
                        self._rec_fps, (w, h))
                if self._rec_writer.isOpened():
                    self._rec_writer.write(overlay)

            if self._udp and (now - self._udp_t_last) >= 1.0 and self._udp_sock:
                self._udp_t_last = now
                akf = self.detector.akf
                pos = akf.x[:3].tolist() if akf.initialized else [0, 0, 0]
                vel = akf.x[3:].tolist() if akf.initialized else [0, 0, 0]
                pkt = {"t": int(now * 1000), "det": data.get("det", False),
                       "conf": data.get("conf", 0.0),
                       "z_raw": data.get("z_raw", 0.0),
                       "z_akf": data.get("z_akf", 0.0),
                       "azim": data.get("azim", 0.0),
                       "elev": data.get("elev", 0.0),
                       "pos": pos, "vel": vel, "fps": self._fps,
                       "status": data.get("status", "--")}
                try:
                    self._udp_sock.sendto(
                        (json.dumps(pkt, ensure_ascii=False) + "\n").encode(),
                        (self._udp_host, self._udp_port))
                except Exception:
                    pass

            self.frame_ready.emit(overlay)
            self.data_ready.emit(data)
            self.fps_update.emit(self._fps)

        if self.cap:
            self.cap.release()
        if self._rec_writer:
            self._rec_writer.release()
        if self._udp_sock:
            self._udp_sock.close()
        self.stop_csv()

    def stop(self, timeout_ms=30000):
        """停止采集。read() 可被立即打断; 若线程正处于首次模型加载
        (detect 内, 冷启动十几秒不可中断), 则分段等待其完成, 避免
        QThread 仍在运行时被析构导致进程 abort。"""
        self._running = False

        def _kick():
            cap = self.cap
            if isinstance(cap, TcpFrameSource):
                try:
                    cap.release()      # notify 打断 read() 条件等待
                except Exception:
                    pass

        _kick()
        deadline = timeout_ms
        while deadline > 0:
            if self.wait(1000):
                return True
            deadline -= 1000
            _kick()
        print("WARN: DetThread 30s 内未结束(模型加载异常?)")
        return False


# ================= 方位距离仪表盘 =================
class AzimGauge(QWidget):
    """罗盘式方位盘(对标样例姿态仪): 指针=目标方位, 中央大字=距离, 外圈=告警色"""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(260, 260)
        self.azim = 0.0
        self.elev = 0.0
        self.range_m = 0.0
        self.level = LV_GRAY

    def set_data(self, azim, elev, range_m, level):
        self.azim, self.elev, self.range_m, self.level = azim, elev, range_m, level
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w / 2, h / 2 - 6, min(w, h) / 2 - 14

        # 外圈告警色
        p.setPen(QPen(QColor(LV_COLOR[self.level]), 4))
        p.setBrush(QColor("#0d1828"))
        p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
        p.setPen(QPen(QColor("#1e3a55"), 1))
        p.drawEllipse(int(cx - r + 14), int(cy - r + 14),
                      int(2 * r - 28), int(2 * r - 28))

        # 刻度
        for deg in range(0, 360, 10):
            a = math.radians(deg - 90)
            major = deg % 30 == 0
            l = 12 if major else 6
            p.setPen(QPen(QColor("#9fc5ff" if major else "#3b5a80"),
                          2 if major else 1))
            p.drawLine(int(cx + (r - 24) * math.cos(a)),
                       int(cy + (r - 24) * math.sin(a)),
                       int(cx + (r - 24 - l) * math.cos(a)),
                       int(cy + (r - 24 - l) * math.sin(a)))

        # N/E/S/W
        p.setPen(QColor("#e6f1ff"))
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        for txt, deg in ((("N", 0), ("E", 90), ("S", 180), ("W", 270))):
            a = math.radians(deg - 90)
            rr = r - 42
            p.drawText(int(cx + rr * math.cos(a)) - 8,
                       int(cy + rr * math.sin(a)) + 5, txt)

        # 方位角标签(10度一档文字省略, 保留30)
        p.setPen(QColor("#7c93ad"))
        p.setFont(QFont("Microsoft YaHei", 7))
        for deg in range(30, 360, 30):
            if deg % 90 == 0:
                continue
            a = math.radians(deg - 90)
            rr = r - 40
            p.drawText(int(cx + rr * math.cos(a)) - 8,
                       int(cy + rr * math.sin(a)) + 3, f"{deg:03d}")

        # 目标指针(azim 右为正 -> 顺时针)
        a = math.radians(self.azim - 90)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(LV_COLOR[self.level]))
        tip = (int(cx + (r - 30) * math.cos(a)),
               int(cy + (r - 30) * math.sin(a)))
        p.drawPolygon(QPolygon([
            QPoint(*tip),
            QPoint(int(cx - 7 * math.sin(a)), int(cy + 7 * math.cos(a))),
            QPoint(int(cx + 7 * math.sin(a)), int(cy - 7 * math.cos(a))),
        ]))

        # 中央距离数字
        p.setBrush(QColor("#0a1424"))
        p.setPen(QPen(QColor("#2b4a73"), 1.5))
        p.drawRoundedRect(int(cx - 62), int(cy - 30), 124, 60, 8, 8)
        p.setPen(QColor("#e6f1ff"))
        p.setFont(QFont("Microsoft YaHei", 22, QFont.Bold))
        txt = f"{self.range_m:.1f}" if self.range_m > 0 else "--"
        p.drawText(int(cx - 62), int(cy - 30), 124, 44,
                   Qt.AlignCenter, txt)
        p.setPen(QColor("#7c93ad"))
        p.setFont(QFont("Microsoft YaHei", 9))
        p.drawText(int(cx - 62), int(cy + 8), 124, 18,
                   Qt.AlignCenter, "距离 m")
        p.end()


# ================= 中央视图: 地图 + 视频浮窗可互换 =================
class CenterView(QWidget):
    def __init__(self, map_view):
        super().__init__()
        self.map = map_view
        self.video = QLabel("等待实时画面…")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("background:#050912; border:1px solid #2b4a73;")
        self.map.setParent(self)
        self.video.setParent(self)
        self._big = "map"      # 谁占满
        self.map.show()
        self.video.show()
        self._last_pix = None
        self._relayout()

    def show_map_big(self):
        self._big = "map"
        self._relayout()

    def show_video_big(self):
        self._big = "video"
        self._relayout()

    def swap(self):
        self.show_video_big() if self._big == "map" else self.show_map_big()

    def set_frame(self, pix):
        self._last_pix = pix
        target = self.video.size()
        self.video.setPixmap(pix.scaled(target, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))

    def resizeEvent(self, ev):
        self._relayout()

    def _relayout(self):
        w, h = self.width(), self.height()
        if self._big == "map":
            self.map.setGeometry(0, 0, w, h)
            self.video.setGeometry(w - 332, h - 200, 320, 188)
            self.map.raise_()
            self.video.raise_()
        else:
            self.video.setGeometry(0, 0, w, h)
            self.map.setGeometry(w - 332, h - 200, 320, 188)
            self.video.raise_()
            self.map.raise_()
        self.map.show()
        self.video.show()


# ================= 目标卡片(对标左栏飞行器卡片) =================
class TargetCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setSpacing(4)
        self.lbl_name = QLabel("可疑目标 UAV-01")
        self.lbl_name.setStyleSheet("font-size:15px; font-weight:bold; color:#e6f1ff;")
        self.lbl_sub = QLabel("视觉检测 · 单目定位")
        self.lbl_sub.setStyleSheet("color:#7c93ad; font-size:11px;")
        row = QHBoxLayout()
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color:#64748b; font-size:16px;")
        self.lbl_state = QLabel("搜索中")
        self.lbl_state.setStyleSheet("font-weight:bold; color:#94a3b8;")
        self.lbl_conf = QLabel("置信度 --")
        self.lbl_conf.setStyleSheet("color:#94a3b8;")
        row.addWidget(self.dot)
        row.addWidget(self.lbl_state)
        row.addStretch()
        row.addWidget(self.lbl_conf)
        self.lbl_range = QLabel("距离 --")
        self.lbl_range.setStyleSheet("font-size:22px; font-weight:bold; color:#e6f1ff;")
        lay.addWidget(self.lbl_name)
        lay.addWidget(self.lbl_sub)
        lay.addLayout(row)
        lay.addWidget(self.lbl_range)

    def update_card(self, det, conf, z, status, level):
        col = LV_COLOR[level]
        self.dot.setStyleSheet(f"color:{col}; font-size:16px;")
        self.lbl_state.setText(LV_TEXT[level])
        self.lbl_state.setStyleSheet(f"font-weight:bold; color:{col};")
        self.lbl_conf.setText(f"置信度 {conf:.2f}" if det else "置信度 --")
        self.lbl_range.setText(f"距离 {z:.1f} m" if det and z > 0 else "距离 --")
        self.setObjectName("CardActive" if det else "Card")
        self.setStyleSheet("")  # 触发 objectName 样式刷新
        self.style().unpolish(self)
        self.style().polish(self)


# ================= 回放页 =================
class ReplayTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.nframes = 0
        self.csv_rows = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.btn_open = QPushButton("打开录像")
        self.btn_csv = QPushButton("关联数据CSV(可选)")
        self.btn_play = QPushButton("播放")
        self.btn_play.setCheckable(True)
        self.btn_open.clicked.connect(self._open_video)
        self.btn_csv.clicked.connect(self._open_csv)
        self.btn_play.clicked.connect(self._toggle_play)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderReleased.connect(self._seek)
        self.lbl_time = QLabel("00:00 / 00:00")
        for b in (self.btn_open, self.btn_csv, self.btn_play):
            bar.addWidget(b)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.lbl_time)
        root.addLayout(bar)

        body = QHBoxLayout()
        self.video = QLabel("选择历史录像回放")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(720, 420)
        self.video.setStyleSheet("background:#050912; border:1px solid #2b4a73;")
        body.addWidget(self.video, 3)

        # 距离曲线
        self.fig = Figure(figsize=(4.2, 4.6), facecolor="#0b1220")
        self.canvas = MplCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._style_ax()
        body.addWidget(self.canvas, 1)
        root.addLayout(body, 1)

    def _style_ax(self):
        ax = self.ax
        ax.set_facecolor("#0b1220")
        ax.tick_params(colors="#7c93ad", labelsize=8)
        for s in ax.spines.values():
            s.set_color("#1e3a55")
        ax.grid(color="#16263c", linewidth=.6)
        self.fig.tight_layout(pad=1.2)

    def _open_video(self):
        path = pick_open_file(self, "选择录像", "视频 (*.mp4 *.avi *.mov *.mkv)")
        if not path:
            return
        self.timer.stop()
        self.btn_play.setChecked(False)
        self.btn_play.setText("播放")
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(path)
        self.nframes = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.fps_v = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.slider.setRange(0, max(self.nframes - 1, 0))
        self._show_current()

    def _open_csv(self):
        path = pick_open_file(self, "选择CSV", "CSV (*.csv)")
        if not path:
            return
        self.csv_rows = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            for r in csv.DictReader(f):
                self.csv_rows.append(r)
        self._plot_curves(0)

    def _plot_curves(self, fi):
        ax = self.ax
        ax.clear()
        self._style_ax()
        if not self.csv_rows:
            ax.set_title("未关联CSV", color="#7c93ad", fontsize=10)
            self.canvas.draw_idle()
            return

        def col(name):
            out = []
            for r in self.csv_rows:
                try:
                    out.append(float(r.get(name, "") or "nan"))
                except ValueError:
                    out.append(float("nan"))
            return out

        zraw = col("z_raw")
        zakf = col("z_akf")
        ztrue = col("z_true") if "z_true" in self.csv_rows[0] else None
        x = np.arange(len(self.csv_rows))
        scale = len(self.csv_rows) / max(self.nframes, 1)
        ax.plot(x / scale if scale else x, zraw, color="#f59e0b", lw=.9, label="RAW")
        ax.plot(x / scale if scale else x, zakf, color="#22c55e", lw=1.1, label="AKF")
        if ztrue is not None:
            ax.plot(x / scale if scale else x, ztrue, color="#60a5fa",
                    lw=.8, ls="--", label="真值")
        ax.axvline(fi, color="#ef4444", lw=1)
        ax.set_xlabel("帧", color="#7c93ad", fontsize=9)
        ax.set_ylabel("距离/m", color="#7c93ad", fontsize=9)
        ax.legend(fontsize=8, facecolor="#0b1220", edgecolor="#1e3a55",
                  labelcolor="#c6d6ea")
        self.canvas.draw_idle()

    def _toggle_play(self, checked):
        if self.cap is None:
            self.btn_play.setChecked(False)
            return
        self.btn_play.setText("暂停") if checked else self.btn_play.setText("播放")
        if checked:
            self.timer.start(int(1000 / max(self.fps_v, 1)))
        else:
            self.timer.stop()

    def _tick(self):
        if self.cap is None:
            return
        ok, fr = self.cap.read()
        if not ok:
            self.timer.stop()
            self.btn_play.setChecked(False)
            self.btn_play.setText("播放")
            return
        self._show_frame(fr)
        fi = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        self.slider.blockSignals(True)
        self.slider.setValue(fi)
        self.slider.blockSignals(False)

    def _seek(self):
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.slider.value())
        self._show_current()

    def _show_current(self):
        if self.cap is None:
            return
        fi = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        ok, fr = self.cap.read()
        if not ok:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, fi)  # peek 后复位
        self._show_frame(fr)

    def _show_frame(self, fr):
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        pix = QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888))
        self.video.setPixmap(pix.scaled(self.video.size(), Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        fi = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        total = self.nframes / max(self.fps_v, 1)
        cur = fi / max(self.fps_v, 1)
        self.lbl_time.setText(f"{cur:05.1f}s / {total:05.1f}s")
        if self.csv_rows:
            self._plot_curves(fi)


# ================= 设置页 =================
class SettingsTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QGridLayout(self)

        g1 = QGroupBox("检测参数(实时生效)")
        l1 = QGridLayout(g1)
        self.sl_conf = QSlider(Qt.Horizontal)
        self.sl_conf.setRange(5, 50)
        self.sl_conf.setValue(20)
        self.lbl_conf = QLabel("0.20")
        self.sl_size = QSlider(Qt.Horizontal)
        self.sl_size.setRange(10, 50)
        self.sl_size.setValue(27)
        self.lbl_size = QLabel("0.270 m")
        l1.addWidget(QLabel("置信度门限"), 0, 0)
        l1.addWidget(self.sl_conf, 0, 1)
        l1.addWidget(self.lbl_conf, 0, 2)
        l1.addWidget(QLabel("无人机等效尺寸"), 1, 0)
        l1.addWidget(self.sl_size, 1, 1)
        l1.addWidget(self.lbl_size, 1, 2)
        root.addWidget(g1, 0, 0)

        g2 = QGroupBox("实时源 / UDP 输出")
        l2 = QGridLayout(g2)
        self.ed_tcp = QLineEdit("tcp://127.0.0.1:14590")
        self.chk_udp = QCheckBox("启用 UDP 输出")
        self.ed_udp = QLineEdit("127.0.0.1:14690")
        l2.addWidget(QLabel("TCP帧流地址"), 0, 0)
        l2.addWidget(self.ed_tcp, 0, 1)
        l2.addWidget(self.chk_udp, 1, 0)
        l2.addWidget(self.ed_udp, 1, 1)
        root.addWidget(g2, 1, 0)

        g3 = QGroupBox("本机定位锚点(视频/摄像头模式为演示坐标)")
        l3 = QGridLayout(g3)
        self.sp_lat = QDoubleSpinBox()
        self.sp_lng = QDoubleSpinBox()
        self.sp_head = QDoubleSpinBox()
        for sp, lo, hi, val in ((self.sp_lat, -90, 90, DEFAULT_ANCHOR[0]),
                                   (self.sp_lng, -180, 180, DEFAULT_ANCHOR[1]),
                                   (self.sp_head, 0, 359.9, 0.0)):
            sp.setRange(lo, hi)
            sp.setDecimals(6)
            sp.setValue(val)
        self.sp_head.setSuffix("°")
        self.rb_sat = QRadioButton("卫星图(需联网)")
        self.rb_radar = QRadioButton("离线雷达态势图")
        self.rb_sat.setChecked(True)
        l3.addWidget(QLabel("纬度"), 0, 0)
        l3.addWidget(self.sp_lat, 0, 1)
        l3.addWidget(QLabel("经度"), 1, 0)
        l3.addWidget(self.sp_lng, 1, 1)
        l3.addWidget(QLabel("本机航向"), 2, 0)
        l3.addWidget(self.sp_head, 2, 1)
        l3.addWidget(self.rb_sat, 3, 0)
        l3.addWidget(self.rb_radar, 3, 1)
        root.addWidget(g3, 2, 0)

        # 配置持久化
        g4 = QGroupBox("配置")
        l4 = QHBoxLayout(g4)
        self.btn_save_cfg = QPushButton("💾 保存配置")
        self.btn_save_cfg.setObjectName("BigBtn")
        self.btn_reset_cfg = QPushButton("恢复默认")
        self.lbl_cfg_tip = QLabel("配置自动保存在程序目录 platform_config.json")
        self.lbl_cfg_tip.setStyleSheet("color:#7c93ad;")
        self.btn_save_cfg.clicked.connect(win._save_config_manual)
        self.btn_reset_cfg.clicked.connect(win._restore_defaults)
        l4.addWidget(self.btn_save_cfg)
        l4.addWidget(self.btn_reset_cfg)
        l4.addWidget(self.lbl_cfg_tip)
        l4.addStretch()
        root.addWidget(g4, 3, 0)
        root.setRowStretch(4, 1)

        self.sl_conf.valueChanged.connect(
            lambda v: (self.lbl_conf.setText(f"{v/100:.2f}"),
                        win.detector and win.detector.set_conf_threshold(v / 100)))
        self.sl_size.valueChanged.connect(
            lambda v: (self.lbl_size.setText(f"{v/100:.3f} m"),
                        win.detector and win.detector.set_drone_size(v / 100)))
        self.sp_lat.valueChanged.connect(self._apply_anchor)
        self.sp_lng.valueChanged.connect(self._apply_anchor)
        self.sp_head.valueChanged.connect(self._apply_anchor)
        self.rb_sat.toggled.connect(
            lambda: win.center.map.set_mode("sat" if self.rb_sat.isChecked()
                                            else "radar"))

    def _apply_anchor(self):
        self.win.center.map.set_anchor(
            self.sp_lat.value(), self.sp_lng.value(), self.sp_head.value())
        self.win.heading = self.sp_head.value()


# ================= 主窗口 =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人机识别与定位系统 DRLS")
        self.resize(1440, 900)
        self.move(0, 0)
        self.detector = DroneDetector()
        self.det_thread = None
        self._det_zombies = []   # 极端情况下未及退出的线程, 保引用防析构崩溃
        self.heading = 0.0
        self._loading = True     # 配置回填期间屏蔽保存逻辑
        self._build()
        self._load_config()
        self._loading = False
        # 界面出来后后台预热模型, 用户点"开始检测"时无需再等十几秒
        threading.Thread(target=self.detector.load_model, daemon=True).start()

    # ---------- 配置持久化 ----------
    def _apply_cfg(self, cfg):
        """把配置 dict 回填到所有控件(控件信号会自动联动检测器/地图)。"""
        s = self.settings
        if cfg["source"] in ("视频文件", "摄像头", "TCP帧流"):
            self.cmb_src.setCurrentText(cfg["source"])
        vp = cfg.get("video_path", "")
        if vp and os.path.isfile(vp):
            self._video_path = vp
        s.sl_conf.setValue(cfg["conf_thr"])
        s.sl_size.setValue(cfg["drone_size"])
        s.ed_tcp.setText(cfg["tcp_addr"])
        s.ed_udp.setText(cfg["udp_addr"])
        self.chk_udp.setChecked(bool(cfg["udp_enabled"]))
        s.sp_lat.setValue(cfg["anchor_lat"])
        s.sp_lng.setValue(cfg["anchor_lng"])
        s.sp_head.setValue(cfg["heading"])
        s._apply_anchor()
        mode = cfg["map_mode"] if cfg["map_mode"] in ("sat", "radar") else "sat"
        s.rb_radar.setChecked(mode == "radar")
        s.rb_sat.setChecked(mode == "sat")
        self.map.set_mode(mode)
        self.detector.set_conf_threshold(cfg["conf_thr"] / 100.0)
        self.detector.set_drone_size(cfg["drone_size"] / 100.0)
        self.resize(cfg["win_w"], cfg["win_h"])

    def _load_config(self):
        try:
            self._apply_cfg(load_config())
        except Exception as e:
            print(f"[config] 加载失败, 使用界面默认值: {e}")

    def _collect_cfg(self):
        s = self.settings
        return {
            "source": self.cmb_src.currentText(),
            "video_path": getattr(self, "_video_path", ""),
            "conf_thr": int(s.sl_conf.value()),
            "drone_size": int(s.sl_size.value()),
            "tcp_addr": s.ed_tcp.text().strip(),
            "udp_enabled": bool(self.chk_udp.isChecked()),
            "udp_addr": s.ed_udp.text().strip(),
            "anchor_lat": s.sp_lat.value(),
            "anchor_lng": s.sp_lng.value(),
            "heading": s.sp_head.value(),
            "map_mode": "radar" if s.rb_radar.isChecked() else "sat",
            "win_w": int(self.width()),
            "win_h": int(self.height()),
        }

    def _save_config(self):
        if self._loading:
            return True
        try:
            save_config(self._collect_cfg())
            return True
        except Exception as e:
            print(f"[config] 保存失败: {e}")
            return False

    def _save_config_manual(self):
        if self._save_config():
            self.statusBar().showMessage("配置已保存到 platform_config.json", 3000)

    def _restore_defaults(self):
        self._loading = True
        try:
            self._apply_cfg(dict(CFG_DEFAULTS))
            self._video_path = ""
        finally:
            self._loading = False
        save_config(dict(CFG_DEFAULTS))
        self.statusBar().showMessage("已恢复默认配置", 3000)

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 顶栏(对标样例) ----------
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(60)
        hh = QHBoxLayout(header)
        hh.setContentsMargins(18, 6, 18, 6)
        title_box = QVBoxLayout()
        t1 = QLabel("无人机识别与定位系统")
        t1.setObjectName("Title")
        t2 = QLabel("DRONE RECOGNITION & LOCALIZATION SYSTEM")
        t2.setObjectName("Subtitle")
        title_box.addWidget(t1)
        title_box.addWidget(t2)
        hh.addLayout(title_box)
        hh.addStretch()
        self.lbl_online = QLabel("● 检测在线")
        self.lbl_online.setStyleSheet("color:#22c55e; font-weight:bold;")
        btn_settings = QPushButton("⚙ 设置")
        btn_settings.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        hh.addWidget(self.lbl_online)
        hh.addWidget(btn_settings)
        root.addWidget(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # ---------- 页1 目标态势 ----------
        live = QWidget()
        live_lay = QHBoxLayout(live)
        live_lay.setContentsMargins(10, 10, 10, 6)

        # 左栏
        left = QVBoxLayout()
        g_targets = QGroupBox("目标列表   1 架")
        gl = QVBoxLayout(g_targets)
        self.card = TargetCard()
        gl.addWidget(self.card)
        left.addWidget(g_targets)

        g_task = QGroupBox("当前任务")
        tl = QGridLayout(g_task)
        self.lbl_src = QLabel("--")
        self.lbl_frames = QLabel("0")
        self.lbl_locktime = QLabel("0 s")
        tl.addWidget(QLabel("视频源"), 0, 0)
        tl.addWidget(self.lbl_src, 0, 1)
        tl.addWidget(QLabel("处理帧"), 1, 0)
        tl.addWidget(self.lbl_frames, 1, 1)
        tl.addWidget(QLabel("累计锁定"), 2, 0)
        tl.addWidget(self.lbl_locktime, 2, 1)
        left.addWidget(g_task)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(250)
        live_lay.addWidget(lw)

        # 中栏: 地图/视频
        self.map = MapView()
        self.center = CenterView(self.map)
        live_lay.addWidget(self.center, 3)

        # 右栏
        right = QVBoxLayout()
        g_gauge = QGroupBox("目标方位 / 距离")
        gg = QVBoxLayout(g_gauge)
        self.gauge = AzimGauge()
        gg.addWidget(self.gauge)
        self.lbl_alarm = QLabel("搜索中")
        self.lbl_alarm.setAlignment(Qt.AlignCenter)
        self.lbl_alarm.setStyleSheet(
            "font-size:16px; font-weight:bold; color:#64748b; padding:4px;")
        gg.addWidget(self.lbl_alarm)
        right.addWidget(g_gauge)

        g_ctrl = QGroupBox("运行控制")
        cl = QVBoxLayout(g_ctrl)
        src_row = QHBoxLayout()
        self.cmb_src = QComboBox()
        self.cmb_src.addItems(["视频文件", "摄像头", "TCP帧流"])
        self.btn_open = QPushButton("打开文件")
        self.btn_open.clicked.connect(self._on_open_file)
        self.cmb_src.currentTextChanged.connect(self._on_src_changed)
        src_row.addWidget(self.cmb_src)
        src_row.addWidget(self.btn_open)
        cl.addLayout(src_row)
        # 初始源为"视频文件", 打开文件按钮可用; 切到 TCP/摄像头 时自动禁用
        self.btn_open.setEnabled(True)
        self.btn_start = QPushButton("▶ 开始检测")
        self.btn_start.setObjectName("BigBtn")
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self._on_toggle)
        self.btn_rec = QPushButton("● 开始录制")
        self.btn_rec.setCheckable(True)
        self.btn_rec.setEnabled(False)
        self.btn_rec.clicked.connect(self._on_rec_toggle)
        self.chk_udp = QCheckBox("UDP 输出 → 127.0.0.1:14690")
        self.chk_udp.toggled.connect(self._on_udp_toggle)
        map_row = QHBoxLayout()
        self.btn_swap = QPushButton("视频/地图 互换")
        self.btn_swap.clicked.connect(self.center.swap)
        self.btn_follow = QPushButton("地图居中")
        self.btn_follow.clicked.connect(self.map.center_anchor)
        map_row.addWidget(self.btn_swap)
        map_row.addWidget(self.btn_follow)
        cl.addWidget(self.btn_start)
        cl.addWidget(self.btn_rec)
        cl.addWidget(self.chk_udp)
        cl.addLayout(map_row)
        # CSV 逐帧记录状态
        self.lbl_csv = QLabel("检测记录: 未开始")
        self.lbl_csv.setStyleSheet("color:#7c93ad; font-size:11px;")
        self.lbl_csv.setWordWrap(True)
        cl.addWidget(self.lbl_csv)
        right.addWidget(g_ctrl)
        right.addStretch()
        rw = QWidget()
        rw.setLayout(right)
        rw.setFixedWidth(310)
        live_lay.addWidget(rw)

        self.tabs.addTab(live, "目标态势")

        # ---------- 页2 回放 ----------
        self.replay = ReplayTab()
        self.tabs.addTab(self.replay, "检测回放")

        # ---------- 页3 设置 ----------
        self.settings = SettingsTab(self)
        self.tabs.addTab(self.settings, "参数设置")
        # 主页与设置页的 UDP 勾选框双向同步(状态一致, 不会递归)
        self.chk_udp.toggled.connect(self.settings.chk_udp.setChecked)
        self.settings.chk_udp.toggled.connect(self.chk_udp.setChecked)

        # ---------- 底部数据条 ----------
        strip = QFrame()
        strip.setObjectName("DataStrip")
        strip.setFixedHeight(56)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(14, 4, 14, 4)
        self.vals = {}
        for key, name in (("range", "AKF距离"), ("raw", "RAW距离"),
                            ("azim", "方位角"), ("elev", "俯仰角"),
                            ("conf", "置信度"), ("status", "状态"),
                            ("fps", "处理帧率"), ("rate", "累计检出率")):
            box = QVBoxLayout()
            k = QLabel(name)
            k.setObjectName("DataKey")
            k.setAlignment(Qt.AlignCenter)
            v = QLabel("--")
            v.setObjectName("DataVal")
            v.setAlignment(Qt.AlignCenter)
            box.addWidget(k)
            box.addWidget(v)
            sl.addLayout(box)
            self.vals[key] = v
        root.addWidget(strip)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪 - 选择视频源后点击 开始检测")

    # ---------- 视频源 ----------
    def _on_src_changed(self, src_type):
        # 只有"视频文件"模式才需要本地文件选择;
        # TCP 地址在"参数设置"页, 摄像头无需选择
        self.btn_open.setEnabled(src_type == "视频文件")
        if src_type == "TCP帧流":
            self.statusBar().showMessage(
                "TCP 实时帧流 - 地址在 参数设置 页配置, 直接点 开始检测")
        elif src_type == "摄像头":
            self.statusBar().showMessage("摄像头模式 - 直接点 开始检测")
        else:
            self.statusBar().showMessage("点击 打开文件 选择视频, 再点 开始检测")

    def _on_open_file(self):
        if self.cmb_src.currentText() != "视频文件":
            self.statusBar().showMessage(
                "当前不是视频文件模式: TCP 地址在 参数设置 页, 摄像头无需选文件")
            return
        path = pick_open_file(self, "选择视频文件",
                              "视频 (*.mp4 *.avi *.mov *.mkv)")
        if path:
            self._video_path = path
            self.statusBar().showMessage(f"已选择: {path}")

    def _on_toggle(self, checked):
        if checked:
            self._start()
        else:
            self._stop()

    def _start(self):
        src_type = self.cmb_src.currentText()
        if src_type == "视频文件":
            if not hasattr(self, "_video_path"):
                self.statusBar().showMessage("请先选择视频文件")
                self.btn_start.setChecked(False)
                return
            path, stype = self._video_path, "file"
        elif src_type == "摄像头":
            path, stype = "0", "camera"
        else:
            path, stype = self.settings.ed_tcp.text().strip(), "tcp"

        # 复用主窗口已预热的检测器, 仅重置本轮统计/滤波状态
        self.detector.reset_stats()
        self.detector.set_conf_threshold(self.settings.sl_conf.value() / 100.0)
        self.detector.set_drone_size(self.settings.sl_size.value() / 100.0)
        self.settings._apply_anchor()

        self.det_thread = DetThread(self.detector)
        self.det_thread.set_source(stype, path)
        self.det_thread.frame_ready.connect(self._on_frame)
        self.det_thread.data_ready.connect(self._on_data)
        self.det_thread.fps_update.connect(self._on_fps)
        self.det_thread.rec_state_changed.connect(lambda r: self.btn_rec.setChecked(r))
        if self.chk_udp.isChecked():
            host, _, port = self.settings.ed_udp.text().partition(":")
            self.det_thread.set_udp(True, host.strip(), int(port or 14690))
        # 每轮检测自动落盘逐帧 CSV (论文实验数据/回放页可关联)
        os.makedirs(RECORDS_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        src_tag = {"file": os.path.basename(path),
                   "camera": "camera", "tcp": f"tcp_{path.split('://')[-1].replace(':','_')}"}[stype]
        csv_path = os.path.join(RECORDS_DIR, f"detect_{ts}_{src_tag}.csv")
        self.det_thread.start_csv(csv_path, src_tag)
        self.det_thread.start()
        self.btn_start.setText("■ 停止检测")
        self.btn_rec.setEnabled(True)
        self.lbl_src.setText(src_type)
        self.lbl_online.setText("● 检测在线")
        self.lbl_online.setStyleSheet("color:#22c55e; font-weight:bold;")
        self.lbl_csv.setText(f"检测记录: records/{os.path.basename(csv_path)}  (0 行)")
        self.statusBar().showMessage(f"运行中 - 源: {src_type} | 记录: {csv_path}")
        self._save_config()        # 开始检测时落盘一次(防崩溃丢配置)

    def _stop(self):
        csv_info = ""
        if self.det_thread:
            th = self.det_thread
            self.det_thread = None
            th.stop_recording()
            stopped = th.stop()
            if not stopped:
                # 极端情况(如模型冷启动未完成): 保留引用防止 QThread
                # 运行中被析构导致崩溃, 线程稍后自行结束
                self._det_zombies.append(th)
            else:
                csv_info = f" | 记录已保存: {th._csv_path} ({th._csv_rows} 行)"
        self.btn_start.setText("▶ 开始检测")
        self.btn_rec.setEnabled(False)
        self.btn_rec.setChecked(False)
        self.btn_rec.setText("● 开始录制")
        if csv_info:
            self.lbl_csv.setText(
                f"检测记录: records/{os.path.basename(th._csv_path)}  "
                f"({th._csv_rows} 行, 已保存)")
        self.statusBar().showMessage("已停止" + csv_info)

    def _on_rec_toggle(self, checked):
        if not self.det_thread:
            self.btn_rec.setChecked(False)
            return
        if checked:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = pick_save_file(
                self, "保存结果视频", "MP4 (*.mp4)",
                os.path.expanduser(f"~/record_{ts}.mp4"))
            if not path:
                self.btn_rec.setChecked(False)
                return
            self.btn_rec.setText("■ 停止录制")
            self.det_thread.start_recording(path)
        else:
            self.btn_rec.setText("● 开始录制")
            self.det_thread.stop_recording()

    def _on_udp_toggle(self, checked):
        if self.det_thread:
            host, _, port = self.settings.ed_udp.text().partition(":")
            self.det_thread.set_udp(checked, host.strip(), int(port or 14690))

    # ---------- 数据回调 ----------
    def _on_frame(self, overlay):
        h, w, _ = overlay.shape
        rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        pix = QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888))
        self.center.set_frame(pix)

    def _on_data(self, d):
        det = bool(d.get("det"))
        # tracked: LOCKED(真实检测) 或 COAST(短时外推维持); 搜索帧不显示目标数据
        tracked = bool(d.get("tracked", det))
        conf = d.get("conf", 0.0)
        z = d.get("z_akf", 0.0) or d.get("z_raw", 0.0)
        z_raw = d.get("z_raw", 0.0)
        azim = d.get("azim", 0.0)
        elev = d.get("elev", 0.0)
        status = d.get("status", "--")
        lvl = alarm_level(tracked, z)

        self.gauge.set_data(azim, elev, z if tracked else 0.0, lvl)
        self.card.update_card(tracked, conf, z, status, lvl)
        self.lbl_alarm.setText(LV_TEXT[lvl])
        self.lbl_alarm.setStyleSheet(
            f"font-size:16px; font-weight:bold; color:{LV_COLOR[lvl]}; padding:4px;")

        self.vals["raw"].setText(f"{z_raw:.2f} m" if det and z_raw else "--")
        self.vals["range"].setText(f"{z:.2f} m" if tracked else "--")
        self.vals["azim"].setText(f"{azim:.2f}°" if tracked else "--")
        self.vals["elev"].setText(f"{elev:.2f}°" if tracked else "--")
        self.vals["conf"].setText(f"{conf:.3f}" if tracked else "--")
        # 状态显示中文化
        self.vals["status"].setText(
            {"LOCKED": "已锁定", "COAST": "预测维持", "SEARCHING": "搜索中"}
            .get(status, status))

        if self.detector and self.detector.total_frames > 0:
            rate = 100.0 * self.detector.det_frames / self.detector.total_frames
            self.vals["rate"].setText(f"{rate:.1f}%")
            self.lbl_frames.setText(str(self.detector.total_frames))
            self.lbl_locktime.setText(
                f"{self.detector.det_frames / max(self.det_thread._fps if self.det_thread else 30, 30):.0f} s")
            # 地图: coast 帧 locked=False(黄色), 搜索帧清除目标点
            self.map.update_target(azim, z, conf, status == "LOCKED", lvl, tracked)
            # 每 15 帧刷新一次 CSV 行数(避免频繁 setText)
            if self.det_thread and self.detector.total_frames % 15 == 0:
                self.lbl_csv.setText(
                    f"检测记录: records/{os.path.basename(self.det_thread._csv_path)}  "
                    f"({self.det_thread._csv_rows} 行)")

    def _on_fps(self, fps):
        self.vals["fps"].setText(f"{fps:.1f}")

    def closeEvent(self, event):
        self._save_config()        # 关窗前最终落盘
        self._stop()
        super().closeEvent(event)


if __name__ == "__main__":
    # cv2 会把 Qt 插件路径改成自己的旧目录, 创建 QApplication 前纠正回 PySide6
    import PySide6
    _plug = os.path.join(os.path.dirname(PySide6.__file__),
                         "Qt", "plugins", "platforms")
    if os.path.isdir(_plug):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plug
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    if len(sys.argv) >= 2:
        w._video_path = sys.argv[1]
        w.cmb_src.setCurrentText("视频文件")
    sys.exit(app.exec())
