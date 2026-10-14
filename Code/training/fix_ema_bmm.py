#!/usr/bin/env python3
"""修复 EMA forward 的 matmul 广播问题：改用显式 bmm（数学等价）"""
SP = "/home/px4/yolo/lib/python3.12/site-packages/ultralytics"
p = f"{SP}/nn/modules/block.py"
src = open(p).read()

OLD = """        x11 = self.softmax(self.agp(x1).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3))
        x12 = x2.reshape(b * self.groups, c // self.groups, -1)
        x21 = self.softmax(self.agp(x2).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3))
        x22 = x1.reshape(b * self.groups, c // self.groups, -1)
        weights = (torch.matmul(x11, x12) + torch.matmul(x21, x22)).reshape(b * self.groups, 1, h, w)"""

NEW = """        x11 = self.softmax(self.agp(x1).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3)).reshape(b * self.groups, 1, -1)
        x12 = x2.reshape(b * self.groups, c // self.groups, h * w)
        x21 = self.softmax(self.agp(x2).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3)).reshape(b * self.groups, 1, -1)
        x22 = x1.reshape(b * self.groups, c // self.groups, h * w)
        weights = (torch.bmm(x11, x12) + torch.bmm(x21, x22)).reshape(b * self.groups, 1, h, w)"""

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    open(p, "w").write(src)
    print("EMA forward fixed with explicit bmm")
elif "torch.baddbmm" in src:
    print("already fixed, skip")
else:
    print("ERROR: anchor not found")
    raise SystemExit(1)
print("FIX_DONE")
