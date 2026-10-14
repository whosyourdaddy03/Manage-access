#!/usr/bin/env python3
"""
E3-video: 从无人机实拍视频做定位评测（无 AprilTag, 无卷尺真值）

策略:
  - 真值: 取连续检出稳态段的距离中位值作为"伪真值"（目标在固定距离悬停段）
  - 对比: 单帧原始 vs 滑动平均 vs 标准KF vs AKF 的 RMSE 和抖动σ
  - 输出: report_materials/e3_video_table.md

用法: ~/yolo/bin/python eval_video3.py
"""
import csv
import os

import numpy as np

from akf_demo import AdaptiveKalmanFilter

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_IN = os.path.join(BASE, "report_materials", "video3_detections.csv")
OUT = os.path.join(BASE, "report_materials", "e3_video_table.md")

# Camera params (no calibration; phone ~60deg FOV @1920px)
FX = 1920 * 0.9   # 1728 px
CX, CY = 960.0, 540.0
DRONE_SIZE = 0.255  # equivalent drone height (m), from sim calibration

WARMUP = 10
MA_WIN = 15


class StandardKF(AdaptiveKalmanFilter):
    """Fixed-R KF for ablation (no Sage-Husa update)."""
    def update(self, z):
        if not self.initialized:
            self.x[:3] = z
            self.initialized = True
            return self.x[:3].copy()
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P
        return self.x[:3].copy()


def load_csv():
    rows = []
    with open(CSV_IN, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def extract_segments(rows):
    """Find continuous detection segments (gap < 15 frames = 0.5s)."""
    segs = []
    cur = []
    for r in rows:
        if r["det"] == 1:
            cur.append(r)
        else:
            if len(cur) >= 30:  # at least 1s of detection
                segs.append(cur)
            cur = []
    if len(cur) >= 30:
        segs.append(cur)
    return segs


def run_filter(seq_3d, seq_t, cls, **kw):
    f = cls(**kw)
    dt = 1.0 / 30.0
    out = np.full((len(seq_3d), 6), np.nan)
    for i, z in enumerate(seq_3d):
        if i > 0:
            dt_t = float(seq_t[i] - seq_t[i - 1])
            if dt_t > 0:
                dt = dt_t
        f.predict(dt)
        f.update(z)
        out[i] = f.x.copy()
    return out


def main():
    rows = load_csv()
    print(f"Loaded {len(rows)} frames from CSV")

    # Extract 3D positions from detection boxes
    det_rows = [r for r in rows if r["det"] == 1]
    print(f"Detected frames: {len(det_rows)}")

    # Build 3D position array (x=azim*dist, y=-elev*dist, z=forward dist)
    # Use box-height distance as forward z, pixel-direct for angle
    seq_3d = []
    seq_t = []
    for r in det_rows:
        bh = r["box_h"]
        if bh < 5:
            continue
        z = DRONE_SIZE * FX / bh
        az = np.radians(r["azim_deg"])
        el = np.radians(r["elev_deg"])
        x = z * np.tan(az)
        y = -z * np.tan(el)
        seq_3d.append(np.array([x, y, z]))
        seq_t.append(r["t_s"])

    seq_3d = np.array(seq_3d)
    seq_t = np.array(seq_t)
    print(f"Valid 3D points: {len(seq_3d)}")

    # Find the longest continuous segment for "pseudo-truth" calibration
    segments = extract_segments(rows)
    if not segments:
        print("[!] No continuous segment >= 30 frames found")
        return

    print(f"\nContinuous segments (>=30 frames):")
    for i, seg in enumerate(segments):
        t0, t1 = seg[0]["t_s"], seg[-1]["t_s"]
        confs = [r["conf"] for r in seg]
        zs = [DRONE_SIZE * FX / max(r["box_h"], 1) for r in seg if r["box_h"] > 5]
        print(f"  seg{i}: f{int(seg[0]['frame'])}-f{int(seg[-1]['frame'])} "
              f"({t0:.1f}s-{t1:.1f}s, {len(seg)} frames) "
              f"conf med={np.median(confs):.2f} "
              f"dist med={np.median(zs):.1f}m" if zs else f"  seg{i}: (no valid boxes)")

    # Use longest segment as pseudo-truth calibration
    # Filter out false-positive segments (box too large = misdetection)
    valid_segs = []
    for seg in segments:
        bhs = [r["box_h"] for r in seg if r["box_h"] > 5]
        if bhs and np.median(bhs) < 200:  # reject segments with huge boxes (misdetection)
            valid_segs.append(seg)
    if not valid_segs:
        print("[!] No valid segment after misdetection filter")
        return
    longest = max(valid_segs, key=len)
    z_truth = np.median([DRONE_SIZE * FX / max(r["box_h"], 1)
                         for r in longest if r["box_h"] > 5])
    print(f"\nPseudo-truth distance (longest segment median): {z_truth:.2f}m")

    # Extract the longest segment's 3D sequence for evaluation
    seg_3d = []
    seg_t = []
    for r in longest:
        bh = r["box_h"]
        if bh < 5:
            continue
        z = DRONE_SIZE * FX / bh
        az = np.radians(r["azim_deg"])
        el = np.radians(r["elev_deg"])
        seg_3d.append(np.array([z * np.tan(az), -z * np.tan(el), z]))
        seg_t.append(r["t_s"])
    seg_3d = np.array(seg_3d)
    seg_t = np.array(seg_t)

    if len(seg_3d) < WARMUP + 20:
        print(f"[!] Longest segment too short after filtering ({len(seg_3d)})")
        return

    # Raw distance
    raw_dist = np.linalg.norm(seg_3d, axis=1)

    # Filtered
    akf_pos = run_filter(seg_3d, seg_t, AdaptiveKalmanFilter, alpha=0.12, q_scale=0.008)
    stk_pos = run_filter(seg_3d, seg_t, StandardKF, alpha=0.12, q_scale=0.008)
    akf_dist = np.linalg.norm(akf_pos[WARMUP:, :3], axis=1)
    stk_dist = np.linalg.norm(stk_pos[WARMUP:, :3], axis=1)

    # Moving average
    ma_dist = np.full(len(seg_3d), np.nan)
    for i in range(len(seg_3d)):
        j0 = max(0, i - MA_WIN + 1)
        ma_dist[i] = np.linalg.norm(seg_3d[j0:i + 1].mean(axis=0))
    ma_dist = ma_dist[WARMUP:]
    raw_w = raw_dist[WARMUP:]

    # Metrics
    raw_rmse = np.sqrt(np.mean((raw_w - z_truth) ** 2))
    ma_rmse = np.sqrt(np.mean((ma_dist - z_truth) ** 2))
    kf_rmse = np.sqrt(np.mean((stk_dist - z_truth) ** 2))
    akf_rmse = np.sqrt(np.mean((akf_dist - z_truth) ** 2))

    raw_std = float(np.std(raw_w))
    akf_std = float(np.std(akf_dist))
    kf_std = float(np.std(stk_dist))

    # Prediction ADE @0.5/1/2s (using AKF velocity state)
    horizons = [0.5, 1.0, 2.0]
    ade_cv = {h: [] for h in horizons}
    ade_akf = {h: [] for h in horizons}
    for h in horizons:
        for i in range(WARMUP, len(seg_3d)):
            j = np.searchsorted(seg_t, seg_t[i] + h)
            if j >= len(seg_3d):
                break
            # Constant-velocity extrapolation
            j0 = max(0, i - MA_WIN + 1)
            if seg_t[i] > seg_t[j0]:
                v = (seg_3d[i] - seg_3d[j0]) / (seg_t[i] - seg_t[j0])
            else:
                v = np.zeros(3)
            cv_pred = seg_3d[i] + v * h
            akf_pred = akf_pos[i, :3] + akf_pos[i, 3:] * h
            ade_cv[h].append(np.linalg.norm(cv_pred - seg_3d[j]))
            ade_akf[h].append(np.linalg.norm(akf_pred - seg_3d[j]))

    # Angle metrics
    az_raw = np.array([np.degrees(np.arctan2(p[0], p[2])) for p in seg_3d[WARMUP:]])
    el_raw = np.array([np.degrees(np.arctan2(-p[1], p[2])) for p in seg_3d[WARMUP:]])
    az_akf = np.array([np.degrees(np.arctan2(p[0], p[2])) for p in akf_pos[WARMUP:, :3]])
    el_akf = np.array([np.degrees(np.arctan2(-p[1], p[2])) for p in akf_pos[WARMUP:, :3]])

    # Write table
    lines = [
        "# E3-video 实拍无人机定位评测",
        "",
        f"数据: 无人机飞行实拍视频 (1920x1080@30fps, {len(seg_3d)}帧连续检出段)",
        f"伪真值: 稳态段距离中位 {z_truth:.2f}m (目标悬停段)",
        f"相机: FX={FX:.0f}px (60°FOV估算), DRONE_SIZE={DRONE_SIZE}m",
        "",
        "## E3: 定位精度（RMSE + 抖动σ）",
        "",
        "| 方法 | 距离RMSE(m) | 抖动σ(m) |",
        "|------|-----------|---------|",
        f"| 单帧原始 | {raw_rmse:.3f} | {raw_std:.4f} |",
        f"| 滑动平均(15帧) | {ma_rmse:.3f} | - |",
        f"| 标准KF(固定R) | {kf_rmse:.3f} | {kf_std:.4f} |",
        f"| **AKF(Sage-Husa)** | **{akf_rmse:.3f}** | **{akf_std:.4f}** |",
        "",
        f"AKF 相比单帧: RMSE ↓{(1-akf_rmse/raw_rmse)*100:.0f}%, "
        f"抖动 ↓{(1-akf_std/raw_std)*100:.0f}%",
        "",
        "## E3b: 短期预测精度（ADE, 伪真值=离线检测距离）",
        "",
        "| 预测时域 | 匀速外推ADE(m) | AKF预测ADE(m) | 改善 | 样本数 |",
        "|----------|--------------|-------------|------|--------|",
    ]

    for h in horizons:
        if ade_cv[h]:
            cv_m = float(np.mean(ade_cv[h]))
            akf_m = float(np.mean(ade_akf[h]))
            imp = (cv_m - akf_m) / cv_m * 100 if cv_m > 0 else 0
            lines.append(f"| {h:.1f}s | {cv_m:.3f} | **{akf_m:.3f}** | {imp:+.1f}% | {len(ade_cv[h])} |")

    lines += [
        "",
        "## E3c: 角度精度（稳态段中位绝对偏差）",
        "",
        "| 方法 | 方位角MAD(°) | 俯仰角MAD(°) |",
        "|------|-------------|-------------|",
        f"| 单帧原始 | {np.median(np.abs(az_raw - np.median(az_raw))):.3f} | "
        f"{np.median(np.abs(el_raw - np.median(el_raw))):.3f} |",
        f"| **AKF平滑** | **{np.median(np.abs(az_akf - np.median(az_akf))):.3f}** | "
        f"**{np.median(np.abs(el_akf - np.median(el_akf))):.3f}** |",
        "",
        "注:",
        f"1. 伪真值距离={z_truth:.2f}m取自连续检出稳态段(帧{int(longest[0]['frame'])}-"
        f"{int(longest[-1]['frame'])}, {len(seg_3d)}帧)的中位值, 目标在此段近似悬停。",
        "2. 相机未标定, FX按60°FOV估算(1920px宽); DRONE_SIZE用仿真域标定值0.255m,",
        "   绝对距离可能有系统偏差, 但AKF的相对平滑效果(RMSE↓/抖动↓)是可靠的。",
        "3. 角度真值取稳态段中位(目标近悬停, 角度应近恒定), MAD=中位绝对偏差。",
    ]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n[OK] {OUT}")
    print(f"\n=== Summary ===")
    print(f"Raw RMSE: {raw_rmse:.3f}m  AKF RMSE: {akf_rmse:.3f}m (↓{(1-akf_rmse/raw_rmse)*100:.0f}%)")
    print(f"Raw σ:    {raw_std:.4f}m  AKF σ:    {akf_std:.4f}m (↓{(1-akf_std/raw_std)*100:.0f}%)")
    for h in horizons:
        if ade_cv[h]:
            print(f"ADE@{h}s: CV={np.mean(ade_cv[h]):.3f}m AKF={np.mean(ade_akf[h]):.3f}m")


if __name__ == "__main__":
    main()
