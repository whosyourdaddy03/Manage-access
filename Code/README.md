# 无人机识别与定位系统（DRLS）

面向反无人机场景的实时态势感知系统：基于 YOLOv8n+P2+EMA 的小目标检测、三态跟踪状态机（遮挡鲁棒）、单目测距与 AKF 平滑、卫星地图态势标注，配套 jMAVSim 仿真闭环（随机航迹 + 静态遮挡物）与 14 用例自动化回归测试。

## 目录结构

```
platform/     大屏系统核心代码（PySide6 三页签：目标态势/检测回放/参数设置）
  drone_platform.py       主程序入口
  platform_detector.py    检测器 + SEARCH/LOCKED/COAST 状态机 + 测距/方位解算
  platform_map.py         Leaflet+Esri 卫星地图桥（内嵌 HTTP 服务器）
  config_store.py         JSON 配置持久化（原子写入）
  tcp_frame_source.py     TCP 帧流适配器（jMAVSim 帧源）
  sim_live.py             仿真闭环算法端（离线版，CSV+UDP 输出）
  live_demo.py            实时检测演示
  run_cases.py            14 用例无头批量测试框架
  verify_state_machine.py 状态机单元验证
  selftest_live.py        GUI 自测驱动
  assets/                 地图前端资源（map.html + Leaflet 1.9.4）

models/
  configs/    YOLOv8n 消融模型配置（baseline / +P2 / +EMA / +P2+EMA）
  weights/    训练权重（含仿真域微调版 p2ema_simft）

training/     训练与仿真域微调
  train_sim_finetune.py   仿真域微调训练脚本
  capture_simdata.py      jMAVSim 帧+真值自动标注采集（450 帧，零手工标注）
  convert_detfly.py       Det-Fly 数据集格式转换
  patch_ema.py / fix_ema_bmm.py  EMA 注意力模块补丁

evaluation/   评测脚本
  eval_e1_extra.py        E1 检测消融（COCO 口径 AP 分尺寸）
  eval_localization.py    E3 自采集数据定位精度（AprilTag 真值）
  calibrate_camera.py / collect_apriltag.py  相机标定与数据采集
  eval_e4_detection_rate.py  E4 光照/模糊退化鲁棒性
  eval_video3.py          实拍视频评测
  gen_charts.py / gen_compare_figures.py / gen_e*_table.py  图表生成

jmavsim/      jMAVSim 仿真器改造（相对上游 PX4/jMAVSim 的改动文件）
  Obstacle.java           静态遮挡物（建筑/树干/电线杆/小屋）
  ScriptedQuad.java       随机航迹目标机（Catmull-Rom 样条 + AABB 避障）
  TruthBroadcaster.java   真值广播（UDP 14680 @50Hz）
  FrameServer.java        护航相机帧推流（TCP 14590 @30fps 720p）
  FixedPoint.java         定点数工具
  Simulator.java          （修改）接入目标机模式 -tg
  Visualizer3D.java       （修改）护航相机跟踪视角

thesis/       毕业论文实验章（LaTeX）
  experiment_chapter.tex  XeLaTeX 编译（ctexart 文档类）
  report_materials/       论文引用图片与结果表
```

## 快速开始

### 1. 仿真闭环（WSL2 + PX4 SITL）

```bash
# jMAVSim 改动合入 PX4-Autopilot/Tools/simulation/jmavsim 后 ant 编译
bash start_closed_loop.sh   # PX4 SITL + jMAVSim（目标机+遮挡物+帧推流）
```

### 2. 大屏平台（WSLg）

```bash
cd platform
DISPLAY=:0 QT_QPA_PLATFORM=xcb \
QTWEBENGINE_DISABLE_SANDBOX=1 \
QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage" \
python drone_platform.py
```

输入源选 TCP帧流（127.0.0.1:14590），点"开始检测"。

### 3. 回归测试

```bash
python run_cases.py            # 14 用例，输出 test_runs/summary.md
```

## 环境

- Windows 11 + WSL2 (Ubuntu 24.04)，Python 3.12，PySide6 6.x
- PyTorch + Ultralytics YOLOv8（CUDA）
- PX4 Autopilot SITL + jMAVSim（本仓库 jmavsim/ 改动）

## 说明

- 模型权重均为 YOLOv8n 量级（~6MB），直接包含在仓库中。
- 大型原始素材（仿真录像、数据集、records/、test_runs/ 原始 CSV）未上传，
  测试结果汇总见 thesis/report_materials/G_test14_summary.md。
