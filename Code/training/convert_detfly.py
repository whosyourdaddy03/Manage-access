# -*- coding: utf-8 -*-
"""
Det-Fly 数据集转换脚本：PASCAL VOC XML → Ultralytics YOLO txt

功能：
  1. 读取 Annotations/<序列>/*.xml，解析 UAV 目标框，转为 YOLO 归一化 txt
  2. 图片以硬链接方式并入数据集目录（同盘秒完成），失败自动降级为复制
  3. train/val 划分：最后一个序列（如 020）按文件名时间序切分——
     前 (1-VAL_RATIO) 训练、后 VAL_RATIO 验证，中间隔 GAP 帧降低时序相关性；
     其余序列（如 010）全部进训练集。杜绝随机切分导致的帧级泄漏
  4. 幂等可重跑：下载完成后重跑一次即可补全，已有输出自动跳过

用法：
  python3 convert_detfly.py                 # 全量转换
  python3 convert_detfly.py --limit 300     # 冒烟测试：每序列只处理前 300 个
"""

import argparse
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# ============================ 配置 ============================
ANN_DIR = Path(r"D:\BaiduNetdiskDownload\Annotations")   # VOC 标注根目录
IMG_DIR = Path(r"D:\BaiduNetdiskDownload\JPEGImages")    # 图片根目录
OUT_DIR = Path(r"D:\Graduate\code\dataset\detfly")       # 输出数据集根目录
CLASSES = {"UAV": 0}                                     # 类别 → YOLO 类别号
VAL_RATIO = 0.15                                         # 最后一个序列中验证集占比
GAP = 100                                                # train/val 之间的间隔帧数
IMG_EXTS = (".jpg", ".jpeg", ".JPG", ".JPEG")
# =============================================================


def P(p: Path) -> Path:
    """路径双端适配：WSL 下自动把 Windows 路径映射为 /mnt/... 形式"""
    if p.exists() or os.name != "posix":
        return p
    s = str(p)
    if len(s) >= 2 and s[1] == ":":
        return Path("/mnt/" + s[0].lower() + s[2:].replace("\\", "/"))
    return p


def parse_xml(xml_path: Path):
    """解析一个 VOC xml，返回 (宽, 高, [(cls_id, cx, cy, w, h), ...])，坐标均为归一化值"""
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    w = int(float(size.find("width").text))
    h = int(float(size.find("height").text))
    if w <= 0 or h <= 0:
        raise ValueError(f"非法图片尺寸 {w}x{h}")
    boxes = []
    for obj in root.iter("object"):
        name = (obj.find("name").text or "").strip()
        if name not in CLASSES:
            continue
        b = obj.find("bndbox")
        xmin = max(0.0, float(b.find("xmin").text))
        ymin = max(0.0, float(b.find("ymin").text))
        xmax = min(float(w), float(b.find("xmax").text))
        ymax = min(float(h), float(b.find("ymax").text))
        if xmax <= xmin or ymax <= ymin:
            continue
        cx = (xmin + xmax) / 2.0 / w
        cy = (ymin + ymax) / 2.0 / h
        bw = (xmax - xmin) / w
        bh = (ymax - ymin) / h
        boxes.append((CLASSES[name], cx, cy, bw, bh))
    return w, h, boxes


def place(src: Path, dst: Path):
    """硬链接并入（同盘瞬时），失败降级为复制；已存在则跳过（幂等）"""
    if dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return True


def main():
    ap = argparse.ArgumentParser(description="Det-Fly VOC→YOLO 转换")
    ap.add_argument("--limit", type=int, default=0, help="每个序列最多处理的 xml 数（0=不限制，冒烟测试用）")
    args = ap.parse_args()

    ann_dir, img_dir, out_dir = P(ANN_DIR), P(IMG_DIR), P(OUT_DIR)
    if not ann_dir.is_dir() or not img_dir.is_dir():
        sys.exit(f"[错误] 输入目录不存在：{ann_dir} 或 {img_dir}")

    seqs = sorted(d for d in ann_dir.iterdir() if d.is_dir())
    if not seqs:
        sys.exit(f"[错误] {ann_dir} 下没有序列子目录")
    val_seq_name = seqs[-1].name  # 字典序最后一个序列用于时序切分验证集
    print(f"[信息] 序列：{[s.name for s in seqs]}；验证集来源：{val_seq_name}（时序后 {int(VAL_RATIO*100)}%，间隔 {GAP} 帧）")

    stats = Counter()
    (out_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)

    for seq in seqs:
        xmls = sorted(seq.glob("*.xml"))
        if args.limit:
            xmls = xmls[: args.limit]
        total = len(xmls)
        cut = int(total * (1 - VAL_RATIO))
        img_seq = img_dir / seq.name

        for i, xml_path in enumerate(xmls):
            base = xml_path.stem
            # 找对应图片
            img_path = next(
                (img_seq / (base + ext) for ext in IMG_EXTS if (img_seq / (base + ext)).exists()),
                None,
            )
            if img_path is None:
                stats["xml 无图片（图片未下载完），跳过"] += 1
                continue
            # 时序切分（仅最后一个序列）
            if seq.name == val_seq_name:
                if i < cut:
                    split = "train"
                elif i >= cut + GAP:
                    split = "val"
                else:
                    stats["间隔帧丢弃"] += 1
                    continue
            else:
                split = "train"

            try:
                _, _, boxes = parse_xml(xml_path)
            except Exception as e:
                stats["xml 解析失败"] += 1
                print(f"[警告] {xml_path.name}: {e}")
                continue

            # 写 YOLO txt（覆盖写，代价极小）
            lbl = out_dir / "labels" / split / f"{base}.txt"
            lbl.parent.mkdir(parents=True, exist_ok=True)
            lbl.write_text("".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n" for c, x, y, w, h in boxes), encoding="utf-8")
            place(img_path, out_dir / "images" / split / img_path.name)
            stats[f"{split} 图片"] += 1
            stats[f"{split} 框"] += len(boxes)
            if (i + 1) % 1000 == 0:
                print(f"  [{seq.name}] {i + 1}/{total}")

        # 无标注图片（负样本）默认不纳入；数量只在汇总里报告
        if args.limit == 0:
            xml_bases = {x.stem for x in seq.glob("*.xml")}
            for ext_group in IMG_EXTS:
                for img in img_seq.glob(f"*{ext_group}"):
                    if img.stem not in xml_bases:
                        stats["无标注图片（未纳入，如需做负样本见脚本说明）"] += 1

    # 写 dataset.yaml
    yaml_path = out_dir / "detfly.yaml"
    yaml_path.write_text(
        f"# Det-Fly → YOLO 数据集配置（由 convert_detfly.py 生成）\n"
        f"# 划分方式：序列 010 全部训练；{val_seq_name} 按时间序前 {int((1-VAL_RATIO)*100)}% 训练、后 {int(VAL_RATIO*100)}% 验证，间隔 {GAP} 帧\n"
        f"path: {out_dir.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n  0: {'UAV'}\n",
        encoding="utf-8",
    )

    print("\n========== 转换汇总 ==========")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"  数据集目录: {out_dir}")
    print(f"  数据集配置: {yaml_path}")
    print("  训练命令示例:")
    print(f"    yolo detect train model=yolov8n.pt data={yaml_path.as_posix()} epochs=100 imgsz=1280 batch=8")


if __name__ == "__main__":
    main()
