"""
YOLOv8 在线推理脚本
用法:
  单张推理: python inference.py --model best.pt --input image.jpg --output result.jpg
  批量推理: python inference.py --model best.pt --input_dir ./images/ --output_dir ./results/
"""
import argparse
import json
import os
import sys
import glob
from pathlib import Path


def run_inference(model_path, input_path, output_path):
    """对单张图片执行推理"""
    try:
        from ultralytics import YOLO
        import cv2
    except ImportError:
        print(json.dumps({"error": "缺少依赖: ultralytics 或 opencv-python"}))
        sys.exit(1)

    if not os.path.exists(model_path):
        print(json.dumps({"error": f"模型文件不存在: {model_path}"}))
        sys.exit(1)

    if not os.path.exists(input_path):
        print(json.dumps({"error": f"输入图片不存在: {input_path}"}))
        sys.exit(1)

    model = YOLO(model_path)
    results = model(input_path, verbose=False)

    for r in results:
        im_array = r.plot()
        cv2.imwrite(output_path, im_array)

    detections = []
    if results and len(results) > 0 and results[0].boxes is not None:
        for box in results[0].boxes:
            detections.append({
                "class": int(box.cls[0].item()),
                "class_name": results[0].names[int(box.cls[0].item())],
                "confidence": round(box.conf[0].item(), 4),
                "bbox": [round(float(x), 2) for x in box.xyxy[0].tolist()]
            })

    output = {
        "detections": detections,
        "count": len(detections),
        "output_path": output_path
    }
    print(json.dumps(output))


def run_batch_inference(model_path, input_dir, output_dir):
    """对目录下所有图片执行批量推理"""
    try:
        from ultralytics import YOLO
        import cv2
    except ImportError:
        print(json.dumps({"error": "缺少依赖: ultralytics 或 opencv-python"}))
        sys.exit(1)

    if not os.path.exists(model_path):
        print(json.dumps({"error": f"模型文件不存在: {model_path}"}))
        sys.exit(1)

    if not os.path.exists(input_dir):
        print(json.dumps({"error": f"输入目录不存在: {input_dir}"}))
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff"]
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(input_dir, ext)))
        image_files.extend(glob.glob(os.path.join(input_dir, ext.upper())))

    image_files.sort()
    total = len(image_files)

    if total == 0:
        print(json.dumps({"error": f"输入目录中未找到图片: {input_dir}", "total": 0}))
        sys.exit(1)

    model = YOLO(model_path)
    all_results = []
    completed = 0

    for img_path in image_files:
        filename = os.path.basename(img_path)
        output_path = os.path.join(output_dir, filename)
        results = model(img_path, verbose=False)

        for r in results:
            im_array = r.plot()
            cv2.imwrite(output_path, im_array)

        detections = []
        if results and len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                detections.append({
                    "class": int(box.cls[0].item()),
                    "class_name": results[0].names[int(box.cls[0].item())],
                    "confidence": round(box.conf[0].item(), 4)
                })

        completed += 1
        all_results.append({
            "file": filename,
            "detections_count": len(detections),
            "output": output_path
        })

        progress = {
            "type": "progress",
            "completed": completed,
            "total": total,
            "percent": round(completed / total * 100, 1),
            "current_file": filename
        }
        print(json.dumps(progress))
        sys.stdout.flush()

    final = {
        "type": "complete",
        "total": total,
        "completed": completed,
        "results": all_results
    }
    print(json.dumps(final))


def main():
    parser = argparse.ArgumentParser(description="YOLOv8 在线推理")
    parser.add_argument("--model", required=True, help="模型文件路径 (best.pt)")
    parser.add_argument("--input", help="输入图片路径 (单张推理)")
    parser.add_argument("--output", help="输出图片路径 (单张推理)")
    parser.add_argument("--input_dir", help="输入目录 (批量推理)")
    parser.add_argument("--output_dir", help="输出目录 (批量推理)")
    args = parser.parse_args()

    if args.input and args.output:
        run_inference(args.model, args.input, args.output)
    elif args.input_dir and args.output_dir:
        run_batch_inference(args.model, args.input_dir, args.output_dir)
    else:
        print(json.dumps({"error": "请指定 --input/--output (单张) 或 --input_dir/--output_dir (批量)"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
