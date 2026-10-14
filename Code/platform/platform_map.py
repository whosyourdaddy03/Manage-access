#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
platform_map: 系统内嵌真实卫星地图 (Leaflet+Esri 瓦片, QWebEngineView)
====================================================================
- 本机位置(锚点): 仿真模式下应来自 px4 SITL 的虚拟GPS(后续扩展 MAVLink 桥);
  当前用可配置的演示锚点(默认 PX4 jMAVSim 默认 home 点苏黎世机场附近)。
- 目标位置: 锚点 + 本机航向 + 我方视觉量测(方位角/距离) 推算经纬度,
  目标位置完全来自检测结果, 不读仿真真值。
- 视频/摄像头模式: 无自身GPS, 使用同一锚点, 界面标注"演示坐标"。
- 无网络时切雷达态势图模式(纯前端 canvas, 离线可用)。
"""
import json
import math
import os
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView

EARTH_R = 6371000.0
DEFAULT_ANCHOR = (47.397742, 8.545594)   # px4 jMAVSim 默认 home
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
HTML_PATH = os.path.join(ASSETS_DIR, "map.html")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _start_assets_server():
    """起一个仅监听 127.0.0.1 的临时静态服务器。
    Chromium 对 file:// 页面会屏蔽远程瓦片(Esri), 用 http://localhost
    源提供 map.html 后瓦片即可正常加载。端口 0 = 系统分配空闲端口。"""
    handler = partial(_QuietHandler, directory=ASSETS_DIR)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    import threading
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return port


ASSETS_PORT = _start_assets_server()
MAP_URL = f"http://127.0.0.1:{ASSETS_PORT}/map.html"


class MapView(QWidget):
    """Leaflet 卫星地图控件, 对上层暴露极简单的更新接口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        lay.addWidget(self.view)
        self._ready = False
        self._pending = []
        self.view.loadFinished.connect(self._on_loaded)
        self.view.setUrl(QUrl(MAP_URL))

        # 状态
        self.anchor_lat, self.anchor_lng = DEFAULT_ANCHOR
        self.heading = 0.0
        self.trail = []          # [[lat,lng], ...]
        self._has_target = False

    def _on_loaded(self, ok):
        self._ready = bool(ok)
        if ok:
            self.set_anchor(self.anchor_lat, self.anchor_lng, self.heading)
            for js in self._pending:
                self.view.page().runJavaScript(js)
            self._pending.clear()

    def _js(self, code):
        if self._ready:
            self.view.page().runJavaScript(code)
        else:
            self._pending.append(code)

    # ---------- 对外接口 ----------
    def set_anchor(self, lat, lng, heading=0.0):
        self.anchor_lat, self.anchor_lng, self.heading = lat, lng, heading
        self.trail.clear()
        self._js(f"setObserver({lat:.8f},{lng:.8f},{heading:.2f});"
                 f"updateTraj([]);")

    def set_mode(self, mode):
        """mode: 'sat' 卫星图 | 'radar' 离线雷达态势图"""
        self._js(f"setMode({json.dumps(mode)});")

    def update_target(self, azim_deg, distance_m, conf, locked, level, visible):
        """按 方位角(相对视轴, 右正)+距离 推算目标经纬度并标点。"""
        if visible and distance_m > 0:
            bearing = math.radians(self.heading + azim_deg)
            d = distance_m
            lat1 = math.radians(self.anchor_lat)
            lng1 = math.radians(self.anchor_lng)
            lat2 = math.asin(math.sin(lat1) * math.cos(d / EARTH_R)
                              + math.cos(lat1) * math.sin(d / EARTH_R) * math.cos(bearing))
            lng2 = lng1 + math.atan2(
                math.sin(bearing) * math.sin(d / EARTH_R) * math.cos(lat1),
                math.cos(d / EARTH_R) - math.sin(lat1) * math.sin(lat2))
            tlat, tlng = math.degrees(lat2), math.degrees(lng2)

            self.trail.append([tlat, tlng])
            if len(self.trail) > 200:
                self.trail.pop(0)
            self._has_target = True
            self._js(
                f"updateTarget({tlat:.8f},{tlng:.8f},{float(conf):.3f},"
                f"{'true' if locked else 'false'},{json.dumps(level)},true);")
            self._js("updateTraj(" + json.dumps(self.trail) + ");")
        else:
            if self._has_target:
                self._js("updateTarget(0,0,0,false,'gray',false);")
                self._has_target = False

    def follow_target(self, enable=True):
        self._js(f"follow({'true' if enable else 'false'});")

    def center_anchor(self):
        self._js("centerObs();")

    def clear_trail(self):
        self.trail.clear()
        self._js("updateTraj([]);")
