#!/usr/bin/env python3
"""
给 ultralytics 添加 EMA 注意力模块（论文创新点之一）
- block.py   : 追加 EMA 类定义（Efficient Multi-Scale Attention, ICASSP 2023）
- __init__.py: 导出 EMA
- tasks.py   : 导入 EMA + parse_model 通道解析分支
幂等：重复运行不会重复插入。
"""
SP = "/home/px4/yolo/lib/python3.12/site-packages/ultralytics"

EMA_CODE = '''

class EMA(nn.Module):
    """Efficient Multi-scale Attention (EMA) module.

    Reference: Cai et al., "Efficient Multi-Scale Attention Module with
    Cross-Spatial Learning", ICASSP 2023.

    Channel-preserving attention: splits channels into groups, extracts
    1D global descriptors along H and W, and performs cross-spatial
    learning between the 1x1 and 3x3 branches.
    """

    def __init__(self, channels, factor=8):
        super().__init__()
        self.groups = factor
        assert channels // self.groups > 0, f"EMA channels {channels} must be >= factor {factor}"
        gn_ch = channels // self.groups
        self.softmax = nn.Softmax(-1)
        self.agp = nn.AdaptiveAvgPool2d((1, 1))
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))
        self.gn = nn.GroupNorm(gn_ch, gn_ch)
        self.conv1x1 = nn.Conv2d(gn_ch, gn_ch, kernel_size=1)
        self.conv3x3 = nn.Conv2d(gn_ch, gn_ch, kernel_size=3, padding=1)

    def forward(self, x):
        b, c, h, w = x.size()
        group_x = x.reshape(b * self.groups, -1, h, w)
        x_h = self.pool_h(group_x)
        x_w = self.pool_w(group_x).permute(0, 1, 3, 2)
        hw = self.conv1x1(torch.cat([x_h, x_w], dim=2))
        x_h, x_w = torch.split(hw, [h, w], dim=2)
        x1 = self.gn(group_x * x_h.sigmoid() * x_w.permute(0, 1, 3, 2).sigmoid())
        x2 = self.conv3x3(group_x)
        x11 = self.softmax(self.agp(x1).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3))
        x12 = x2.reshape(b * self.groups, c // self.groups, -1)
        x21 = self.softmax(self.agp(x2).reshape(b * self.groups, -1, 1, 1).permute(0, 2, 1, 3))
        x22 = x1.reshape(b * self.groups, c // self.groups, -1)
        weights = (torch.matmul(x11, x12) + torch.matmul(x21, x22)).reshape(b * self.groups, 1, h, w)
        return (group_x * weights.sigmoid()).reshape(b, c, h, w)
'''

# ---------- 1. block.py ----------
p = f"{SP}/nn/modules/block.py"
src = open(p).read()
if "class EMA" in src:
    print("block.py: EMA already present, skip")
else:
    if not src.endswith("\n"):
        src += "\n"
    open(p, "w").write(src + EMA_CODE)
    print("block.py: EMA class appended")

# ---------- 2. __init__.py ----------
p = f"{SP}/nn/modules/__init__.py"
src = open(p).read()
if "from .block import EMA" in src:
    print("__init__.py: already exported, skip")
else:
    open(p, "a").write("\nfrom .block import EMA  # EMA attention (custom addition)\n")
    print("__init__.py: EMA exported")

# ---------- 3. tasks.py ----------
p = f"{SP}/nn/tasks.py"
src = open(p).read()
changed = False
if "from ultralytics.nn.modules import EMA" not in src:
    src = src.replace(
        "from ultralytics.nn.modules import (",
        "from ultralytics.nn.modules import EMA  # EMA attention (custom addition)\nfrom ultralytics.nn.modules import (",
        1,
    )
    changed = True
    print("tasks.py: import added")
else:
    print("tasks.py: import already present, skip")

OLD = """        elif m is AIFI:
            args = [ch[f], *args]"""
NEW = """        elif m is EMA:  # channel-preserving attention (custom addition)
            c2 = ch[f]
            args = [c2, *args]
        elif m is AIFI:
            args = [ch[f], *args]"""
if OLD in src and "elif m is EMA:" not in src:
    src = src.replace(OLD, NEW, 1)
    changed = True
    print("tasks.py: parse_model branch added")
elif "elif m is EMA:" in src:
    print("tasks.py: parse_model branch already present, skip")
else:
    print("tasks.py: WARNING - AIFI anchor not found!")

if changed:
    open(p, "w").write(src)

print("PATCH_DONE")
