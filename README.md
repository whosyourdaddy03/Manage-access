# Manage-access

面向学术研究的PX4双地面站项目：保留官方QGroundControl用于PX4配置、校准与人工接管，使用Vue 3、FastAPI和ROS 2构建自主飞行研究地面站。

## 当前内容

- [`ground_station/`](./ground_station/)：Vue 3前端、FastAPI网关、模拟PX4遥测、安全状态机和ROS 2/PX4适配骨架；
- [`ground_station_design/`](./ground_station_design/)：PX4双地面站系统方案与安全状态机设计；
- [`RuoYi-Vue/`](./RuoYi-Vue/)：早期后台管理与可视化参考实现；
- [`UAVPerception.drawio`](./UAVPerception.drawio)：早期架构图。

基础框架默认使用模拟适配器，不会向真实PX4发送飞行指令。启动与验证方法见[`ground_station/README.md`](./ground_station/README.md)。

## 历史记录

20260705

首次添加

开源无人机生态系统地面控制站：https://robotics.growbotics.ai/zh/projects/software/qgroundcontrol

无人机全自主飞行开源框架 GAAS 的主要结构与功能：https://gaas.gitbook.io/guide/software-realization-build-your-own-autonomous-drone/gaas-zong-lan

20260707

了解 QGroundControl 和 GAAS 的基础内容及功能，并开始绘制大致结构图
