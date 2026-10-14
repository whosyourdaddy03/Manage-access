#!/usr/bin/env python3
"""
p2ema 模型仿真域 finetune: 用 sim_finetune (450帧, 真值自动标注) 消除尺度OOD死区
策略: 小数据集域适应 -> 低LR + 少epoch + 关闭mosaic(保护中心目标尺度信息)
用法: ~/yolo/bin/python train_sim_finetune.py
"""
from ultralytics import YOLO

MODEL = "/mnt/d/Graduate/code/runs/p2ema_v8n/weights/best.pt"
DATA = "/mnt/d/Graduate/sim_finetune/data.yaml"
RUN_NAME = "p2ema_simft"

model = YOLO(MODEL)

results = model.train(
    data=DATA,
    name=RUN_NAME,
    epochs=20,
    batch=8,
    imgsz=640,
    lr0=0.001,            # 低学习率, 基于预训练权重微调
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,
    warmup_momentum=0.8,
    warmup_bias_lr=0.05,
    # 数据增强: 关闭mosaic(目标在画面中心, mosaic会破坏尺度学习), 保留适度翻转/缩放
    mosaic=0.0,
    mixup=0.0,
    hsv_h=0.015,
    hsv_s=0.5,
    hsv_v=0.4,
    degrees=0.0,          # 不旋转(目标姿态有意义)
    translate=0.05,
    scale=0.3,
    shear=0.0,
    perspective=0.0,
    flipud=0.0,
    fliplr=0.5,
    # 训练稳定
    patience=10,
    save=True,
    save_period=5,
    plots=True,
    val=True,
    workers=4,
    device=0,
    verbose=True,
)

print("\n[train] finetune 完成")
print(f"[train] best weights: runs/detect/{RUN_NAME}/weights/best.pt")
