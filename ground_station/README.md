# PX4 双地面站基础框架

本目录实现“官方 QGroundControl + Web 研究地面站”的第一版基础工程。QGC 负责 PX4 固件配置、校准、参数管理和人工接管；本工程负责科研遥测、任务请求、视觉追踪、算法实验及 ROS 2 自主飞行链路。

当前版本默认使用模拟飞行适配器，已经打通：

```text
Vue 3 仪表盘 → REST/WebSocket → FastAPI → 模拟 PX4 + 安全状态机
                                      ↓
                             ROS 2/PX4 接口骨架
```

## 目录

```text
ground_station/
├── web/                 # Vue 3 + TypeScript + Vite
├── api/                 # FastAPI、WebSocket、命令幂等、模拟适配器
├── ros2_ws/src/
│   ├── uav_interfaces/  # FlightStatus.msg、SubmitCommand.srv
│   ├── uav_safety/      # 安全状态机与命令门
│   └── px4_adapter/     # uXRCE-DDS只读遥测适配器
├── config/safety.yaml   # 安全阈值占位配置
├── docker-compose.yml
└── Makefile
```

## 本地运行

要求 Python 3.10+、Node.js 20+。打开两个终端：

```bash
cd ground_station
make api-install
make api-run
```

```bash
cd ground_station
make web-install
make web-run
```

浏览器访问 <http://localhost:5173>，API文档位于 <http://localhost:8000/docs>。

也可以使用容器：

```bash
cd ground_station
docker compose up --build
```

容器模式访问 <http://localhost:8080>。

## 演示流程

模拟适配器支持下面的安全状态路径：

```text
连接 PX4 → 解锁 → 起飞至悬停 → 开始追踪 → 暂停追踪 → 受控降落
```

命令不满足当前状态时会被拒绝；急停进入锁定状态，只能通过人工复位返回。

## API契约

- `GET /api/v1/health`：服务状态；
- `GET /api/v1/vehicles/primary/telemetry`：最新遥测；
- `POST /api/v1/commands`：提交高层飞行命令；
- `WS /api/v1/ws/telemetry`：10 Hz实时遥测。

浏览器不得提交电机PWM、推力、姿态或高频速度指令。真实Offboard控制仅允许ROS 2安全节点发布。

## ROS 2与PX4接入

建议在 Ubuntu 24.04、ROS 2 Jazzy 和匹配版本的 `px4_msgs` 环境中构建：

```bash
cd ground_station/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 run px4_adapter px4_telemetry_adapter
ros2 run uav_safety safety_supervisor
```

基础版本的 `px4_adapter` 只读取 `/fmu/out/vehicle_status`，`uav_safety` 不发送飞控指令。这是有意设置的安全边界，不代表PX4实机控制已经完成。

## 下一阶段

1. 在 PX4 SITL 中验证 uXRCE-DDS遥测；
2. 实现 FastAPI到ROS 2服务/话题的桥接；
3. 根据PX4实际ACK更新状态，不再使用立即状态转换；
4. 完成Offboard心跳、setpoint、超时悬停/降落和控制权仲裁；
5. 接入视频、YOLO、目标跟踪、TD3和rosbag2；
6. 通过SITL测试后，才允许低风险实机验证。

## Git策略

- `ground_station/`：主仓库普通目录；
- PX4、QGC、GAAS和其他第三方源码：单独克隆或通过 `.repos` 清单固定版本，不复制到本目录；
- `node_modules`、ROS 2构建目录、模型、rosbag和ULog：不提交。
