# PX4无人机地面站设计文档

本目录保存“官方 QGroundControl + Web研究地面站”的方案和安全设计。运行代码位于 [`ground_station`](../ground_station/README.md)。

## 技术路线

- 飞控：PX4；
- 配置与人工地面站：官方QGroundControl，不修改源码；
- 研究地面站：Vue 3 + TypeScript；
- 服务网关：FastAPI；
- 自主飞行：ROS 2 Jazzy + PX4 uXRCE-DDS；
- 自主算法：GAAS架构思想 + YOLO + 目标跟踪 + TD3；
- 数据：rosbag2、PX4 ULog和实验元数据库。

## 文档

1. [系统方案设计](./系统方案设计.md)
2. [安全状态机设计](./安全状态机设计.md)

## Git约定

- 自研 `ground_station/` 与本设计目录采用主仓库普通目录；
- 本地参考仓库 `Manage-access/` 和 `reference_repos/` 加入忽略规则；
- PX4、QGC、GAAS、`px4_msgs` 等第三方源码不复制进自研目录；
- 后续需要固定ROS依赖时使用 `.repos` 清单记录仓库地址和Commit。
