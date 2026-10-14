#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_store: DRLS 平台参数持久化
=================================
把用户在界面上调整的参数保存到程序目录下 platform_config.json,
下次启动自动恢复。文件缺失/损坏时静默回退默认值, 不影响启动。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "platform_config.json")

# 默认参数(与界面控件初始值保持一致)
DEFAULTS = {
    "source": "视频文件",            # 视频文件 / 摄像头 / TCP帧流
    "video_path": "",               # 上次选择的视频文件
    "conf_thr": 20,                 # 置信度门限滑块(百分数 5~50)
    "drone_size": 27,               # 等效尺寸滑块(value/100 = 0.27 m)
    "tcp_addr": "tcp://127.0.0.1:14590",
    "udp_enabled": False,
    "udp_addr": "127.0.0.1:14690",
    "anchor_lat": 47.397742,        # jMAVSim Irchel 公园 home
    "anchor_lng": 8.545594,
    "heading": 0.0,
    "map_mode": "sat",              # sat / radar
    "win_w": 1440,
    "win_h": 900,
}


def load_config(path=CONFIG_PATH):
    """读取配置; 缺失/损坏/字段非法时用默认值补齐, 永远返回完整 dict。"""
    cfg = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        if isinstance(user, dict):
            for k, v in user.items():
                if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
                    cfg[k] = v
    except FileNotFoundError:
        pass
    except Exception:
        # JSON 损坏等: 用默认值启动, 下次保存会覆盖修复
        print(f"[config] 配置文件无法解析, 使用默认值: {path}")
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    """原子写入: 先写临时文件再替换, 防止写一半时断电损坏。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
