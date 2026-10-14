#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成论文用曲线图（从 test_runs CSV 数据绘图）。"""
import csv, glob, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 中文字体
for p in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
          "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
          "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(p):
        fm.fontManager.addfont(p)
        break
plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
                                    "Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = "/mnt/d/Graduate/code"
OUT = os.path.join(BASE, "report_materials")
TR = os.path.join(BASE, "test_runs")

# 配色
C_LOCK = "#22c55e"    # 绿
C_COAST = "#f59e0b"   # 橙
C_SEARCH = "#ef4444"  # 红
C_LINE1 = "#3b82f6"   # 蓝
C_LINE2 = "#f97316"   # 橙线

def load_case(cid):
    fs = sorted(glob.glob(os.path.join(TR, f"case{cid:02d}_*.csv")))
    if not fs: return None
    return list(csv.DictReader(open(fs[0], encoding="utf-8")))

def get_stats(rows):
    from collections import Counter
    c = Counter(r["status"] for r in rows)
    n = len(rows)
    lock = c.get("LOCKED",0)/n
    coast = c.get("COAST",0)/n
    search = c.get("SEARCHING",0)/n
    track = lock + coast
    return dict(lock=lock, coast=coast, search=search, track=track, n=n)

# ============ 图1: 门限扫描 ============
fig, ax = plt.subplots(figsize=(7, 4.5))
confs = [0.20, 0.35, 0.50]
locks, tracks = [], []
for c in confs:
    cid = {0.20:6, 0.35:7, 0.50:8}[c]
    rows = load_case(cid)
    if rows:
        s = get_stats(rows)
        locks.append(s["lock"]*100)
        tracks.append(s["track"]*100)
    else:
        locks.append(0); tracks.append(0)
ax.plot(confs, locks, "o-", color=C_LINE1, lw=2, ms=8, label="锁定率 (LOCKED)")
ax.plot(confs, tracks, "s-", color=C_LINE2, lw=2, ms=8, label="航迹保持率 (LOCKED+COAST)")
ax.set_xlabel("置信度门限", fontsize=12)
ax.set_ylabel("百分比 (%)", fontsize=12)
ax.set_title("置信度门限对检测性能的影响", fontsize=14)
ax.set_xticks(confs)
ax.set_ylim(0, 110)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
for x, y in zip(confs, locks):
    ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points",
                xytext=(0, 10), ha="center", fontsize=10)
for x, y in zip(confs, tracks):
    ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points",
                xytext=(0, 10), ha="center", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "G_chart_threshold_scan.png"), dpi=200)
plt.close()
print("图1: 门限扫描 -> G_chart_threshold_scan.png")

# ============ 图2: 尺寸敏感 ============
fig, ax = plt.subplots(figsize=(7, 4.5))
sizes = [0.230, 0.270, 0.310]
z_mins, z_means, z_maxs = [], [], []
for s in sizes:
    cid = {0.230:9, 0.270:2, 0.310:10}[s]
    rows = load_case(cid)
    if rows:
        zs = [float(r["z_akf"]) for r in rows
              if r["status"] in ("LOCKED","COAST") and float(r["z_akf"])>0]
        if zs:
            z_mins.append(min(zs)); z_means.append(np.mean(zs)); z_maxs.append(max(zs))
        else:
            z_mins.append(0); z_means.append(0); z_maxs.append(0)
    else:
        z_mins.append(0); z_means.append(0); z_maxs.append(0)
ax.errorbar(sizes, z_means, yerr=[np.array(z_means)-np.array(z_mins),
            np.array(z_maxs)-np.array(z_means)], fmt="o-", color=C_LINE1,
            lw=2, ms=8, capsize=6, label="平均距离 ± 范围")
ax.set_xlabel("等效尺寸 (m)", fontsize=12)
ax.set_ylabel("测距结果 (m)", fontsize=12)
ax.set_title("等效尺寸对测距结果的影响", fontsize=14)
ax.set_xticks(sizes)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
for x, y in zip(sizes, z_means):
    ax.annotate(f"{y:.1f}m", (x, y), textcoords="offset points",
                xytext=(0, 10), ha="center", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "G_chart_size_sensitivity.png"), dpi=200)
plt.close()
print("图2: 尺寸敏感 -> G_chart_size_sensitivity.png")

# ============ 图3: TCP遮挡场景状态分布堆叠柱状图 ============
fig, ax = plt.subplots(figsize=(7, 5))
labels = ["C11\n第1轮", "C12\n第2轮", "C13\n第3轮"]
lock_p, coast_p, search_p = [], [], []
for cid in [11, 12, 13]:
    rows = load_case(cid)
    if rows:
        s = get_stats(rows)
        lock_p.append(s["lock"]*100)
        coast_p.append(s["coast"]*100)
        search_p.append(s["search"]*100)
    else:
        lock_p.append(0); coast_p.append(0); search_p.append(0)
x = np.arange(len(labels))
w = 0.6
b1 = ax.bar(x, lock_p, w, color=C_LOCK, label="LOCKED (已锁定)")
b2 = ax.bar(x, coast_p, w, bottom=lock_p, color=C_COAST, label="COAST (预测维持)")
b3 = ax.bar(x, search_p, w, bottom=np.array(lock_p)+np.array(coast_p),
            color=C_SEARCH, label="SEARCHING (搜索中)")
ax.set_ylabel("帧占比 (%)", fontsize=12)
ax.set_title("TCP 实时遮挡场景状态分布 (COAST=1.0s)", fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 115)
ax.legend(fontsize=10, loc="upper right")
# 标注保持率
for i in range(3):
    total = lock_p[i] + coast_p[i]
    ax.text(i, total + 2, f"保持率\n{total:.1f}%", ha="center", fontsize=10,
            fontweight="bold", color=C_LINE2)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "G_chart_tcp_state_dist.png"), dpi=200)
plt.close()
print("图3: TCP状态分布 -> G_chart_tcp_state_dist.png")

# ============ 图4: COAST优化对比 ============
fig, ax = plt.subplots(figsize=(7, 4.5))
cases = ["C11", "C12", "C13"]
before = [75.0, 75.2, 83.3]  # COAST=0.6s
after = [88.9, 90.7, 94.5]   # COAST=1.0s
x = np.arange(len(cases))
w = 0.3
b1 = ax.bar(x - w/2, before, w, color="#94a3b8", label="COAST=0.6s (优化前)")
b2 = ax.bar(x + w/2, after, w, color=C_LINE1, label="COAST=1.0s (优化后)")
ax.set_ylabel("航迹保持率 (%)", fontsize=12)
ax.set_title("COAST 预算优化效果对比", fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels(cases)
ax.set_ylim(0, 115)
ax.legend(fontsize=11)
for i in range(3):
    ax.annotate(f"{before[i]:.1f}%", (i - w/2, before[i]),
                textcoords="offset points", xytext=(0, 5), ha="center", fontsize=9)
    ax.annotate(f"{after[i]:.1f}%", (i + w/2, after[i]),
                textcoords="offset points", xytext=(0, 5), ha="center", fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "G_chart_coast_optimization.png"), dpi=200)
plt.close()
print("图4: COAST优化对比 -> G_chart_coast_optimization.png")

# ============ 图5: 14用例总览 ============
fig, ax = plt.subplots(figsize=(10, 5))
all_ids = list(range(1, 15))
all_lock, all_track = [], []
for cid in all_ids:
    rows = load_case(cid)
    if rows:
        s = get_stats(rows)
        all_lock.append(s["lock"]*100)
        all_track.append(s["track"]*100)
    else:
        all_lock.append(0); all_track.append(0)
x = np.arange(len(all_ids))
w = 0.35
colors_lock = [C_LOCK if l >= 80 else "#fbbf24" if l >= 50 else C_SEARCH
               for l in all_lock]
b1 = ax.bar(x - w/2, all_lock, w, color=colors_lock, alpha=0.8, label="锁定率")
b2 = ax.bar(x + w/2, all_track, w, color=C_LINE1, alpha=0.8, label="航迹保持率")
# 标注跳过的C14
if all_lock[13] == 0:
    ax.text(13, 5, "跳过", ha="center", fontsize=9, color="#94a3b8")
ax.set_ylabel("百分比 (%)", fontsize=12)
ax.set_title("14 用例检测结果总览", fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels([f"C{cid:02d}" for cid in all_ids])
ax.set_ylim(0, 115)
ax.legend(fontsize=11, loc="upper right")
ax.axhline(y=70, color=C_LINE2, ls="--", lw=1.5, alpha=0.7, label="合格线 70%")
# 区域标注
ax.axvspan(-0.5, 2.5, alpha=0.08, color=C_LOCK, label="")
ax.axvspan(2.5, 9.5, alpha=0.08, color="#fbbf24", label="")
ax.axvspan(9.5, 12.5, alpha=0.08, color=C_COAST, label="")
ax.text(1, 108, "录像基线", ha="center", fontsize=9, color="#64748b")
ax.text(6, 108, "特性刻画", ha="center", fontsize=9, color="#64748b")
ax.text(11, 108, "TCP遮挡", ha="center", fontsize=9, color="#64748b")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "G_chart_overview.png"), dpi=200)
plt.close()
print("图5: 14用例总览 -> G_chart_overview.png")

print("\n全部完成，5 张图已保存到 report_materials/")
