#!/usr/bin/env python3
"""
E1 补强：FPS 测量 + AP_small/medium/large（COCO 面积口径）
对 4 个模型在 Det-Fly 验证集上统一评测，结果追加到 e1_table.md

用法: ~/yolo/bin/python eval_e1_extra.py [--skip-ap]
注意: 需 GPU；AP 评测单模型约几分钟（937 张 4K 图, imgsz=640）
"""
import argparse
import csv
import json
import os
import time

import numpy as np

RUNS = "/mnt/d/Graduate/code/runs"
VAL_DIR = "/mnt/d/Graduate/code/dataset/detfly/images/val"
LBL_DIR = "/mnt/d/Graduate/code/dataset/detfly/labels/val"
OUT_MD = "/mnt/d/Graduate/code/report_materials/e1_table.md"
GT_JSON = "/mnt/d/Graduate/code/report_materials/_val_gt_coco.json"
RES_JSON = "/mnt/d/Graduate/code/report_materials/_e1_extra.json"

MODELS = [
    ("YOLOv8n（基线）", f"{RUNS}/preview_v8n-4/weights/best.pt"),
    ("+P2", f"{RUNS}/p2_v8n/weights/best.pt"),
    ("+EMA", f"{RUNS}/ema_v8n/weights/best.pt"),
    ("+P2+EMA（本文方法）", f"{RUNS}/p2ema_v8n/weights/best.pt"),
]


def build_gt_json():
    """把 YOLO txt 标签转成 COCO gt json（原图 4K 坐标，COCO bbox=左上xywh）"""
    from PIL import Image
    W, H = 3840, 2160
    images, annotations = [], []
    files = sorted(f for f in os.listdir(VAL_DIR) if f.lower().endswith(".jpg"))
    for i, f in enumerate(files):
        img_id = i + 1
        im = Image.open(os.path.join(VAL_DIR, f))
        assert im.size == (W, H), f"{f} 尺寸 {im.size} 与假设不符"
        images.append({"id": img_id, "file_name": f, "width": W, "height": H})
        lbl = os.path.join(LBL_DIR, os.path.splitext(f)[0] + ".txt")
        if not os.path.exists(lbl):
            continue
        for line in open(lbl):
            c, cx, cy, bw, bh = map(float, line.split())
            annotations.append({
                "id": len(annotations) + 1,
                "image_id": img_id,
                "category_id": 1,
                "bbox": [(cx - bw / 2) * W, (cy - bh / 2) * H, bw * W, bh * H],
                "area": bw * W * bh * H,
                "iscrowd": 0,
            })
    gt = {"images": images, "annotations": annotations,
          "categories": [{"id": 1, "name": "UAV"}]}
    with open(GT_JSON, "w") as fp:
        json.dump(gt, fp)
    print(f"GT json: {len(images)} 图 / {len(annotations)} 框 -> {GT_JSON}")
    return [im["file_name"] for im in images]


def evaluate_ap(model, files):
    """推理全部验证图 -> COCO 风格按 GT 面积分桶 AP@0.5（small/medium/large）
    桶阈值与 COCO 一致：small<32^2, medium<96^2, large>=96^2（原图 4K 像素面积）
    匹配规则：score 降序贪心，IoU>=0.5，每个 GT 只匹配一次"""
    name2id = {f: i + 1 for i, f in enumerate(files)}
    dets = []
    t0 = time.time()
    for n, f in enumerate(files):
        r = model.predict(os.path.join(VAL_DIR, f), imgsz=640, conf=0.001,
                          iou=0.7, max_det=300, verbose=False,
                          device=0)[0]
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        for (x1, y1, x2, y2), cf in zip(boxes, confs):
            dets.append({"image_id": name2id[f], "category_id": 1,
                         "bbox": [float(x1), float(y1),
                                  float(x2 - x1), float(y2 - y1)],
                         "score": float(cf)})
        if (n + 1) % 200 == 0:
            el = time.time() - t0
            print(f"  推理 {n+1}/{len(files)}  {el:.0f}s")
    with open(GT_JSON) as fp:
        gt = json.load(fp)

    def iou(a, b):
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2, bx2, by2 = ax1 + aw, ay1 + ah, bx1 + bw, by1 + bh
        iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
        ih = max(0.0, min(ay2, by2) - max(ay1, by1))
        inter = iw * ih
        return inter / (aw * ah + bw * bh - inter + 1e-9)

    gt_by_img = {}
    for a in gt["annotations"]:
        gt_by_img.setdefault(a["image_id"], []).append(a)

    def ap_at(bucket):
        """bucket: (lo, hi) GT 面积区间 [px^2)"""
        lo, hi = bucket
        g = {i: [a for a in anns if lo <= a["area"] < hi]
             for i, anns in gt_by_img.items()}
        n_gt = sum(len(v) for v in g.values())
        if n_gt == 0:
            return None
        used = {i: [False] * len(v) for i, v in g.items()}
        d = [x for x in dets if x["image_id"] in g]
        d.sort(key=lambda x: -x["score"])
        tp = np.zeros(len(d))
        fp = np.zeros(len(d))
        for k, det in enumerate(d):
            best_iou, best_j = 0.5, -1
            for j, a in enumerate(g[det["image_id"]]):
                if used[det["image_id"]][j]:
                    continue
                v = iou(det["bbox"], a["bbox"])
                if v > best_iou:
                    best_iou, best_j = v, j
            if best_j >= 0:
                used[det["image_id"]][best_j] = True
                tp[k] = 1
            else:
                fp[k] = 1
        ctp, cfp = np.cumsum(tp), np.cumsum(fp)
        rec = ctp / n_gt
        prec = ctp / np.maximum(ctp + cfp, 1e-9)
        # 101 点插值（COCO 方式）
        ap = 0.0
        for t in np.linspace(0, 1, 101):
            p = prec[rec >= t]
            ap += p.max() if len(p) else 0.0
        return ap / 101 * 100

    return {"AP50": ap_at((0, 1e10)), "AP_small": ap_at((0, 32 ** 2)),
            "AP_medium": ap_at((32 ** 2, 96 ** 2)), "AP_large": ap_at((96 ** 2, 1e10))}


def measure_fps(model, frames):
    """GPU 单帧 FPS（batch=1, imgsz=640）。帧已预载内存，排除磁盘 IO 干扰，
    含预处理+推理+后处理，四模型完全同条件"""
    import torch
    for f in frames[:8]:
        model.predict(f, imgsz=640, conf=0.25, verbose=False, device=0)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t0 = time.time()
    for f in frames[8:]:
        model.predict(f, imgsz=640, conf=0.25, verbose=False, device=0)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    return len(frames[8:]) / (time.time() - t0)


def update_table(results):
    """重写 e1_table.md：mAP/P/R 取 results.csv 最优 epoch（官方验证协议），
    FPS/AP 分尺寸/参数量取评测结果（与历史 json 合并）"""
    lines = [
        "# E1 检测对比表（Det-Fly 验证集，imgsz=640）",
        "",
        "| 模型 | 参数量(M) | mAP50(%) | mAP50-95(%) | Precision(%) | Recall(%) "
        "| FPS | AP_small(%) | AP_medium(%) | AP_large(%) |",
        "|------|----------|----------|-------------|--------------|-----------"
        "|-----|-------------|--------------|-------------|",
    ]
    for name, rd in MODELS:
        csvp = rd.replace("/weights/best.pt", "") + "/results.csv"
        row = None
        if os.path.isfile(csvp):
            rows = list(csv.DictReader(open(csvp)))
            row = max(rows, key=lambda r: float(r["metrics/mAP50-95(B)"]))
        r = results.get(name, {})
        def g(k, fmt="{:.1f}"):
            return fmt.format(r[k]) if k in r and r[k] is not None else "-"
        m50 = f"{float(row['metrics/mAP50(B)'])*100:.1f}" if row else "-"
        m5095 = f"{float(row['metrics/mAP50-95(B)'])*100:.1f}" if row else "-"
        prec = f"{float(row['metrics/precision(B)'])*100:.1f}" if row else "-"
        rec = f"{float(row['metrics/recall(B)'])*100:.1f}" if row else "-"
        lines.append(
            f"| {name} | {g('params', '{:.2f}')} | {m50} | {m5095} | {prec} | {rec} "
            f"| {g('fps')} | {g('AP_small')} | {g('AP_medium')} | {g('AP_large')} |")
    lines += [
        "",
        "注：mAP50/mAP50-95/Precision/Recall 为 Ultralytics 官方验证协议（results.csv 中 mAP50-95 最优 epoch）；",
        "FPS 为 RTX 4060 batch=1（帧预载内存，含预处理与后处理）；",
        "AP 分尺寸按 COCO 面积口径（small<32²px，medium<96²px，large≥96²px，IoU=0.5，101 点插值）。",
    ]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[OK] 表格已更新 -> {OUT_MD}")
    print("\n".join(lines))


def merge_and_save(results):
    """与历史结果 json 合并（AP 结果可跨次运行保留）"""
    if os.path.exists(RES_JSON):
        old = json.load(open(RES_JSON))
        for k, v in old.items():
            results.setdefault(k, {}).update(
                {kk: vv for kk, vv in v.items() if kk not in results.get(k, {})})
    os.makedirs(os.path.dirname(RES_JSON), exist_ok=True)
    json.dump(results, open(RES_JSON, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ap", action="store_true", help="只测 FPS（合并历史 AP）")
    ap.add_argument("--models", type=str, default=None,
                    help="逗号分隔子集序号，如 0,3 （默认全部）")
    args = ap.parse_args()

    from ultralytics import YOLO
    idx = [int(i) for i in args.models.split(",")] if args.models else range(4)
    files = sorted(f for f in os.listdir(VAL_DIR) if f.lower().endswith(".jpg"))

    if not args.skip_ap and not os.path.exists(GT_JSON):
        files = build_gt_json()

    # FPS 用帧预载内存，排除 4K JPEG 磁盘读取的缓存干扰
    import cv2
    frames = [cv2.imread(os.path.join(VAL_DIR, f)) for f in files[:48]]

    results = {}
    for i in idx:
        name, pt = MODELS[i]
        print(f"\n===== [{i}] {name} =====")
        model = YOLO(pt)
        results[name] = {"fps": measure_fps(model, frames)}
        print(f"FPS: {results[name]['fps']:.1f}")
        if not args.skip_ap:
            ap_res = evaluate_ap(model, files)
            if ap_res:
                results[name].update(ap_res)
                print(f"AP50={ap_res['AP50']:.1f}  APs={ap_res['AP_small']:.1f} "
                      f"APm={ap_res['AP_medium']:.1f} APl={ap_res['AP_large']:.1f}")
        # 参数量
        n_params = sum(p.numel() for p in model.model.parameters())
        results[name]["params"] = n_params / 1e6

    merge_and_save(results)
    results = json.load(open(RES_JSON))
    update_table(results)


if __name__ == "__main__":
    main()
