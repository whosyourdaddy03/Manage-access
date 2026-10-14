#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tcp_frame_source: jMAVSim FrameServer 实时帧流适配器
====================================================
背景:
  jMAVSim 离屏 FrameServer 推送的是自定义分帧协议, 不是标准 RTSP/HTTP 流,
  cv2.VideoCapture("tcp://127.0.0.1:14590") 无法打开。
  本模块把 sim_live.py 中已验证的手写 socket 收帧逻辑抽成独立类,
  对外暴露与 cv2.VideoCapture 相同的 isOpened()/read()/release() 接口,
  供 drone_platform.DetThread 无侵入替换。

协议:
  服务端对每帧发送: b"FRAME <ts_ms> <w> <h> <jpeg_len>\n" + jpeg_bytes

实时特性:
  - 数据由对端主动推送, 本端不能预读、不能拖进度条;
  - 丢旧保新: 接收线程只缓存最新一帧, 处理跟不上时自动丢帧保时延;
  - read() 阻塞等下一帧(条件变量唤醒), 无新帧超时返回 (False, None)
    供上层检查退出标志, 不忙等;
  - 断线自动重连(每 0.5s), 服务端晚启动也能接上。
"""
import socket
import threading
import time
from urllib.parse import urlparse

import cv2
import numpy as np


class TcpFrameSource:
    """jMAVSim 自定义 TCP 帧流源, 接口对齐 cv2.VideoCapture。"""

    def __init__(self, host="127.0.0.1", port=14590, timeout=1.0):
        self.host = host
        self.port = int(port)
        self.timeout = timeout            # read() 等新帧的超时(秒)

        self._running = True
        self._cond = threading.Condition()
        self._latest = None               # (ts_ms, jpeg_bytes)
        self._seq = 0                     # 接收帧自增序号
        self._consumed_seq = 0            # read() 已取走的序号
        self._connected = False

        self._th = threading.Thread(target=self._receiver, daemon=True)
        self._th.start()

    # -------- 工厂: 解析 "tcp://host:port" --------
    @staticmethod
    def from_path(path):
        if path.startswith("tcp://"):
            u = urlparse(path)
            return TcpFrameSource(u.hostname or "127.0.0.1",
                                  u.port or 14590)
        # 兜底: 允许直接传 "host:port"
        host, _, port = path.partition(":")
        return TcpFrameSource(host or "127.0.0.1", int(port or 14590))

    # -------- 接收线程: 连接 / 解帧 / 丢旧保新 / 重连 --------
    def _receiver(self):
        while self._running:
            buf = b""
            c = None
            try:
                c = socket.create_connection((self.host, self.port), timeout=3)
                self._connected = True
                while self._running:
                    pkt = c.recv(65536)
                    if not pkt:
                        break
                    buf += pkt
                    # 一帧 = 一行头部 + 定长 jpeg
                    while b"\n" in buf:
                        header, rest = buf.split(b"\n", 1)
                        parts = header.decode("ascii", "ignore").split()
                        if parts[0] != "FRAME" or len(parts) != 5:
                            buf = rest
                            continue
                        ln = int(parts[4])
                        if len(rest) < ln:
                            break                   # 帧未到齐, 等下次 recv
                        with self._cond:
                            # 丢旧保新: 只留最新一帧
                            self._latest = (int(parts[1]), rest[:ln])
                            self._seq += 1
                            self._cond.notify_all()
                        buf = rest[ln:]
            except Exception:
                pass
            finally:
                if c is not None:
                    try:
                        c.close()
                    except Exception:
                        pass
                self._connected = False
            # 断线/服务端未启动: 0.5s 后重连
            if self._running:
                time.sleep(0.5)

    # -------- 对外接口(对齐 VideoCapture) --------
    def isOpened(self):
        # 后台线程会持续重连, 即使服务端尚未启动也视为"已打开(待连)"
        return self._running

    def read(self):
        """阻塞等下一帧。
        返回 (True, bgr_frame) 或 (False, None)(超时/退出/解码失败)。
        """
        if not self._running:
            return False, None
        with self._cond:
            ok = self._cond.wait_for(
                lambda: self._seq > self._consumed_seq or not self._running,
                timeout=self.timeout)
            if not ok or self._seq <= self._consumed_seq:
                return False, None
            ts_ms, jpeg = self._latest
            self._consumed_seq = self._seq
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        with self._cond:
            self._running = False
            self._cond.notify_all()
        self._th.join(timeout=1.5)

    # -------- 状态查询(供 UI 显示连接状态) --------
    def is_connected(self):
        return self._connected

    @property
    def frame_count(self):
        return self._seq
