#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态机确定性验证: 用脚本化假检测框驱动 DroneDetector.detect(),
验证 SEARCH 高门限初锁 / 最近邻维持 / JUMP_GATE / Z_GATE / COAST 超时。
不加载真实模型(model 被替换为返回预设框的假对象)。"""
import sys, math
sys.path.insert(0, "/mnt/d/Graduate/code")
import numpy as np
import platform_detector as pd_mod
from platform_detector import DroneDetector

FRAME = np.zeros((480, 640, 3), np.uint8)

class Arr:
    def __init__(self, a): self.a = np.asarray(a, np.float32)
    def cpu(self): return self
    def numpy(self): return self.a

class Boxes:
    def __init__(self, xyxy, conf):
        self.xyxy = Arr(xyxy)
        self.conf = Arr(conf)
    def __len__(self): return len(self.conf.a)

class Result:
    def __init__(self, boxes): self.boxes = boxes

class FakeModel:
    """脚本帧: 每帧返回 (xyxy列表, conf列表); None=空帧。"""
    def __init__(self): self.script = []
    def __call__(self, frame, conf=0.10, verbose=False):
        item = self.script.pop(0)
        if item is None:
            return [Result(Boxes(np.zeros((0,4)), np.zeros(0)))]
        xyxy, confs = item
        return [Result(Boxes(xyxy, confs))]

def box(cx, cy, bh, bw=None):
    bw = bw or bh
    return [cx - bw/2, cy - bh/2, cx + bw/2, cy + bh/2]

# z=5m 对应 bh(fx≈554, size=0.27): bh = 0.27*554/5 ≈ 29.9
det = DroneDetector()
det.load_model = lambda: None          # 跳过真实模型加载
det.model = FakeModel()
det.fx = (640/2)/math.tan(math.pi/6); det.cx, det.cy = 320, 240
det._set_camera(FRAME)

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, flush=True)

# 帧1: conf 0.30 中心框 -> 低于0.55, 必须仍是 SEARCH
det.model.script.append(([box(320,240,30)], [0.30]))
_, d = det.detect(FRAME)
check("低置信0.30不初锁", d["status"] == "SEARCHING" and not d["det"])

# 帧2: conf 0.60 中心框 -> LOCKED
det.model.script.append(([box(320,240,30)], [0.60]))
_, d = det.detect(FRAME)
check("高置信0.60初锁", d["status"] == "LOCKED" and d["det"] and d["tracked"])
z0 = d["z_raw"]

# 帧3: 目标移动50px, 新位置0.80 + 旧位置附近0.30 -> 最近邻选附近(维持)
det.model.script.append(([box(370,240,30), box(150,100,30)], [0.30, 0.90]))
_, d = det.detect(FRAME)
check("最近邻维持(不跳至高置信远框)", d["status"]=="LOCKED" and abs((d["x1"]+d["x2"])/2-370)<2)

# 帧4: 高置信远框 250px 外 -> 超 JUMP_GATE, 无 picked -> COAST
det.model.script.append(([box(370+250,240,30)], [0.95]))
_, d = det.detect(FRAME)
check("跳变>140px拒绝->COAST", d["status"]=="COAST" and d["tracked"] and not d["det"])

# 帧5: 立刻回来 -> 重新 LOCKED
det.model.script.append(([box(370,240,30)], [0.80]))
_, d = det.detect(FRAME)
check("外推期目标回来->LOCKED", d["status"]=="LOCKED")

# 帧6-7: 连续空帧, 模拟时间快进超过0.6s -> 回 SEARCH
orig_time = pd_mod.time.time
t = {"v": orig_time() + 0.3}  # 先快进0.3s
det.model.script += [None, None]
pd_mod.time.time = lambda: t["v"]
_, d1 = det.detect(FRAME)                      # miss 0.3s -> COAST
check("丢帧0.3s内COAST", d1["status"]=="COAST")
t["v"] += 0.5
_, d2 = det.detect(FRAME)                      # 累计0.8s -> SEARCH
check("丢帧超0.6s回SEARCH", d2["status"]=="SEARCHING" and det.last_box is None)
pd_mod.time.time = orig_time
det._t_prev = None

# 帧8: 重新初锁
det.model.script.append(([box(320,240,30)], [0.70]))
_, d = det.detect(FRAME)
check("搜索后重新初锁", d["status"]=="LOCKED")

# 帧9: 测距突变(z 翻倍: bh 减半), 高置信, 连续6帧 -> 第5帧后触发滤波器重置, 不丢锁
for i in range(6):
    det.model.script.append(([box(320,240,15)], [0.70]))  # bh 30->15, z≈2x
statuses = []
for i in range(6):
    _, dd = det.detect(FRAME)
    statuses.append(dd["status"])
check("Z_GATE拒绝6帧期间不丢锁(重置滤波器)", all(s=="LOCKED" for s in statuses))

# 帧10: 低质量测距连续拒绝15帧(conf<0.5) -> 放弃航迹
det.last_z = 100.0   # 人为制造后续量测全部超门限
for i in range(15):
    det.model.script.append(([box(320,240,30)], [0.30]))
dropped = False
for i in range(15):
    _, dd = det.detect(FRAME)
    if dd["status"] == "SEARCHING":
        dropped = True; break
check("连续15帧异常量测->放弃航迹", dropped)

# 帧11: 候选低于维持门限0.20 不进候选 -> SEARCH 不变
det.model.script.append(([box(320,240,30)], [0.15]))
_, d = det.detect(FRAME)
check("conf 0.15低于维持门限被过滤", d["status"]=="SEARCHING")

ok_all = all(ok for _, ok in results)
print("ALL_PASS" if ok_all else "HAS_FAIL", flush=True)
sys.exit(0 if ok_all else 1)
