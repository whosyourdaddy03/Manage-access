#!/usr/bin/env python3
"""
E1 检测对比表自动生成：从 runs 目录汇总各模型指标
输出 Markdown 表格（论文可直接引用格式），纯 CPU 运行，训练中也能跑
用法：~/yolo/bin/python gen_e1_table.py
"""
import csv
import os
import torch

RUNS = "/mnt/d/Graduate/code/runs"
OUT = "/mnt/d/Graduate/code/report_materials/e1_table.md"

MODELS = [
    ("YOLOv8n（基线）", f"{RUNS}/preview_v8n-4"),
    ("+P2", f"{RUNS}/p2_v8n"),
    ("+EMA", f"{RUNS}/ema_v8n"),
    ("+P2+EMA（本文方法）", f"{RUNS}/p2ema_v8n"),
]


def best_row(csv_path):
    """取 results.csv 中 mAP50-95 最高的行"""
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    best = max(rows, key=lambda r: float(r["metrics/mAP50-95(B)"]))
    return best, len(rows)


def count_params(pt_path):
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    m = ckpt.get("model")
    if m is None:
        m = ckpt.get("ema")
    if m is None:
        return 0
    return sum(p.numel() for p in m.parameters())


def main():
    lines = [
        "# E1 检测对比表（Det-Fly 验证集，imgsz=640）",
        "",
        "| 模型 | 参数量(M) | mAP50(%) | mAP50-95(%) | Precision(%) | Recall(%) |",
        "|------|----------|----------|-------------|--------------|-----------|",
    ]
    missing = []
    for name, rd in MODELS:
        csvp = f"{rd}/results.csv"
        ptp = f"{rd}/weights/best.pt"
        if not (os.path.isfile(csvp) and os.path.isfile(ptp)):
            missing.append(name)
            continue
        try:
            row, _ = best_row(csvp)
            params = count_params(ptp)
        except Exception as e:
            missing.append(f"{name} (error: {e})")
            continue
        lines.append(
            f"| {name} | {params/1e6:.2f} "
            f"| {float(row['metrics/mAP50(B)'])*100:.1f} "
            f"| {float(row['metrics/mAP50-95(B)'])*100:.1f} "
            f"| {float(row['metrics/precision(B)'])*100:.1f} "
            f"| {float(row['metrics/recall(B)'])*100:.1f} |"
        )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    if missing:
        print(f"\n(尚未完成: {', '.join(missing)} — 训练完成后重跑本脚本即可补全)")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
