# originbot_navigation 功能包结构说明

> 学习用文档：帮助理解 OriginBot 的 SLAM 建图与自主导航。
> 代码位置：`originbot_navigation/`，**纯配置包**（无任何手写源码），全部由 launch + yaml/lua 配置驱动官方算法。
> 阅读前提：`originbot_base`（odom/TF 来源）与 `originbot_driver`（/scan 来源）的接口。

---

## 一、包的定位

把三大导航方案**声明式**地装配起来：

1. **Cartographer SLAM**（2D 激光建图，输出 `/map`）；
2. **robot_localization EKF**（融合 odom 与 IMU，输出平滑的里程估计）；
3. **Nav2**（基于 `/map` 的路径规划与导航）。

一切以"改配置、套参数"的形式完成，不写业务代码。

## 二、目录结构

```
originbot_navigation/
├── launch/
│   ├── cartographer.launch.py      # Cartographer 前端+后端+占位栅格节点
│   ├── occupancy_grid.launch.py    # cartographer_occupancy_grid_node
│   ├── odom_ekf.launch.py          # robot_localization 的 ekf_node
│   └── nav_bringup.launch.py       # Nav2 全家桶入口
├── config/
│   ├── ekf.yaml                    # EKF 融合配置
│   └── lds_2d.lua                  # Cartographer 配置（2D 雷达）
├── param/
│   └── originbot_nav2.yaml         # Nav2 全套参数（代价地图/规划器/行为…）
└── maps/
    └── my_map.{pgm,yaml}           # 预存地图（可视化/Marker）
```

## 三、四大 launch 详解

### 1. `odom_ekf.launch.py` —— 里程数据融合

```
Node(robot_localization / ekf_node, name=ekf_filter_node,
     parameters=[config/ekf.yaml, {use_sim_time}])
```

- **输入**：`odom0: /odom`（底盘里程计，必需）；
- **输出**：`/odometry/filtered` + **odom→base_footprint TF**（替代底盘自产 TF）；
- `ekf.yaml` 关键项：

| 参数 | 值 | 含义 |
|---|---|---|
| `odom0` | `odom` | 融合的里程话题 |
| `odom0_config` | 前6位 x,y,*,*,*,yaw 与 vx,vy,*,*,*,vz 均为 true | 选取位姿+线/角速度共 12 维 |
| `odom0_queue_size` | 10 | 订阅队列 |
| `world_frame` | `odom` | 世界坐标系（连续、无跳变） |
| `base_link_frame` | `base_footprint` | 机器人本体系 |

> 若未来接入 IMU，只需在 yaml 增加 `imu0: imu` 与 `imu0_config`，EKF 即可自动融合 IMU 高频姿态，这就是"配置即融合"的妙处。

### 2. `cartographer.launch.py` —— 2D 激光建图

```
cartographer_node (前端子系统) + cartographer_occupancy_grid_node + rviz 可选
参数: configuration_basename=lds_2d.lua
      resolution=0.05, publish_period_sec=1.0
```

- **输入**：`/scan`（vp100 雷达）、odom + base_footprint TF；
- **输出**：`/map`（栅格地图）、`/map_metadata`、Cartographer 轨迹；
- `lds_2d.lua` 为 2D 雷达适配的经典配置（含子图划分、回环检测等数值）。

### 3. `occupancy_grid.launch.py` —— 栅格地图补充发布

```
cartographer_occupancy_grid_node [-resolution 0.05] [-publish_period_sec 1.0]
```

- 把 Cartographer 子图序列化输出为 `nav_msgs/OccupancyGrid (/map)`，供 Nav2 使用；
- 实际常被 `cartographer.launch.py` 联动启动。

### 4. `nav_bringup.launch.py` —— Nav2 导航全家桶

```
IncludeLaunchDescription(nav2_bringup/bringup_launch.py,
    map=<maps/my_map.yaml>, params_file=<param/originbot_nav2.yaml>)
```

- 一行 `include` 拉起 **map_server、AMCL(定位)、planner_server、controller_server、
  behavior_server、waypoint_follower、costmap 2024 (global/local)**…… 全部由 Nav2 官方包承担；
- 对外暴露 **Action**：`/navigate_to_pose`（被 `originbot_example/originbot_send_goal` 调用）；
- 输出 `/cmd_vel` 驱动底盘。

## 四、`param/originbot_nav2.yaml` 核心配置速读

| 分组 | 关键点 |
|---|---|
| controller_server | 局部路径规划（DWB adapted），输出 `/cmd_vel` |
| local/global_costmap | `robot_radius: 0.08`、`/scan` 作障碍观测源、inflation_radius 0.1（全局膨胀） |
| planner_server | `navfn_planner（A* 风格全局规划）`, `tolerance 0.5` |
| behavior_server | spin / backup / drive_on_heading / wait 四种恢复行为 |
| waypoint_follower | 多航点任务执行 (wait_at_waypoint) |
| map_server | `yaml_filename: turtlebot3_world.yaml`（模板值，实际以 launch 传入 map 为准） |

> 注意 `originbot_nav2.yaml` 中 `map_server.yaml_filename` 仍是模板值 `turtlebot3_world.yaml`（来自 Nav2 官方模板），真正生效的地图由 launch 参数 `map` 传入，说明该包在**最小化修改官方模板**的基础上只做了"增量覆盖"。

## 五、数据流全景

```
            ┌─ originbot_base ──► /odom ─────┐
            │                                ▼
 VP100雷达 ──► /scan ──► Cartographer ──► /map ──► Nav2(map+amcl)
            └─ /odom ──► EKF ──► /odometry/filtered & TF
                                                 │
                              /navigate_to_pose ◄┘(Action 目标)
                                                 ▼ send_goal 示例
                                                 └─► /cmd_vel ──► base
```

## 六、学习提示

1. 本包是教科书级的"**组合式导航配置**"范例：装 `originbot_base` + `vp100_ros2` 的驱动、写三份配置、套官方算法即得完整 SLAM+导航；
2. 三套坐标：Cartographer 出 `map`，EKF 出 `odom→base_footprint`，静态 TF 由底盘包/雷达包给出 `base_footprint→base_link→laser_link`；
3. 调试常用命令：`ros2 topic echo /map`、`ros2 service call /map_server/load_map`、RViz2 加载 `nav2_bringup` 的 rviz 配置观察 costmap。

## 七、速查表

- **建图**：`ros2 launch originbot_navigation cartographer.launch.py`
- **EKF**：`ros2 launch originbot_navigation odom_ekf.launch.py`
- **导航**：`ros2 launch originbot_navigation nav_bringup.launch.py`
- **发送目标**：`ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose:{...}}"`
- **地图**：`maps/my_map.{pgm,yaml}`；**Nav2 参数**：`param/originbot_nav2.yaml`。