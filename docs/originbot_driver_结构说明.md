# originbot_driver 功能包结构说明

> 学习用文档：帮助理解 OriginBot 设备驱动层的组成。
> 代码位置：`originbot_driver/`，是一个**逻辑集散地**（元目录），内部其实是三个相互独立的子包/库，无聚合 CMakeLists。
> 阅读本文前建议先读完 [`originbot_base_结构说明.md`](./originbot_base_结构说明.md)，理解串口帧协议背景。

---

## 一、包的定位

`originbot_driver` 收纳机器人的**底层设备驱动**，分三类：

| 子项 | 类型 | 说明 |
|---|---|---|
| `serial_ros2` | ROS2 包（纯库） | 跨平台串口通信库 `serial` 的 ROS2 port，被 `originbot_base` 以 `find_package(serial)` 依赖 |
| `vp100_ros2` | ROS2 包（节点+库） | VP100 激光雷达驱动，含 `nvilidar` 厂商 SDK，发布 `/scan` |
| `qpOASES` | 第三方源码树 | 开源 QP(二次规划)求解器库，随仓库供货（本课堂代码未直接编译使用） |

```
originbot_driver/
├── serial_ros2/     # 串口驱动包 (project: serial)
├── vp100_ros2/      # VP100 激光雷达包
└── qpOASES/         # 第三方 QP 求解器（离线算法库）
```

## 二、serial_ros2 —— 串口通信库

### 作用

给上层提供阻塞式读写的串口 API。`originbot_base` 构造函数中即通过它操作 `/dev/ttyS3`：

```cpp
serial_.setPort("/dev/" + port_name);            // 选择串口
serial_.setBaudrate(115200);                     // 波特率
serial::Timeout t = serial::Timeout::simpleTimeout(2000);
serial_.setTimeout(t);
serial_.open();                                  // 打开
serial_.read(&rx_data, 1);                       // 逐字节读（找帧头）
serial_.write(&frame.header, sizeof(frame));     // 整帧写
```

### 目录结构

```
serial_ros2/
├── include/serial/
│   ├── serial.h          # 主接口（Serial/Timeout 类）
│   └── impl/unix.h, win.h, v8stdint.h
└── src/
    ├── serial.cc
    ├── impl/unix.cc, win.cc
    └── impl/list_ports/list_ports_{linux,osx,win}.cc   # 端口枚举
```

- 构建出 `libserial` 共享库（`ament_export_libraries`），因此下游依赖名是 **`serial`**（`find_package(serial REQUIRED)`）。
- 派生自 wjwwood/serial（ROS1 经典方案），本仓库为 ROS2 适配版。

## 三、vp100_ros2 —— VP100 激光雷达驱动

### 作用

通过串口（默认 `/dev/ttyUSB0` @ 230400）管理 VP100 激光雷达，完成初始化、旋转扫描、滤波，并发布标准 `sensor_msgs/LaserScan` 到 `/scan`，供导航建图使用。

### 目录结构

```
vp100_ros2/
├── src/
│   ├── vp100_ros2_node.cpp     # 驱动主节点（LifecycleNode 风格）+ 主循环
│   └── vp100_ros2_client.cpp   # 调试订阅工具：打印 scan 的角度-距离
├── sdk/src/nvilidar/           # 厂商 SDK 核心
│   ├── nvilidar_driver_serialport.{h,cpp}   # 串口协议收发
│   ├── nvilidar_process.{h,cpp}             # 周期采样、点云生成、滤波
│   └── nvilidar_protocol.h / nvilidar_filter.h  # 协议常量 & 滤波
├── sdk/src/impl/src/serial/    # SDK 内部串口实现（unix/win）
├── launch/{vp100_launch.py, vp100_launch_view.py, vp100.py}
├── params/vp100.yaml
├── startup/initenv.sh
└── sdk/samples/main.cpp        # 独立示例
```

### 关键流程（node）

```
读取参数(serialport_name/baud/frame_id/angle_*/range_*)
   → new LidarProcess(串口名, 230400, 时间戳回调)
   → LidarReloadPara(cfg)         # 应用参数
   → LidarInitialialize()         # 握手初始化
   → LidarTurnOn()                # 启动扫描
   → create_publisher<LaserScan>("scan", SensorDataQoS)
   → 50Hz 循环 { LidarSamplingProcess(scan) → 封装 LaserScan → publish }
```

- 发布话题：`/scan`（`sensor_msgs/LaserScan`），`frame_id` 默认 `laser_link`；
- **LifecycleNode**：节点带生命周期管理（unconfigured→inactive→active），可由 launch 或外部工具切换状态；
- `vp100_launch.py` 同时启动 `tf2_ros/static_transform_publisher`，发布 `base_link → laser_link`（z≈0.02m）静态 TF；
- `vp100_ros2_client` 是独立的调试程序，订阅 `/scan` 逐点打印角度-距离。

### 参数（params/vp100.yaml 节选）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `serialport_name` | `/dev/ttyUSB0` | 雷达串口 |
| `serialport_baud` | `230400` | 波特率 |
| `frame_id` | `laser_link` | 扫描数据坐标系 |
| `angle_min/max` | `-180 / 180` | 角度范围(度) |
| `range_min/max` | `0.001 / 64.0` | 量程(米)，64m 是协议上限，实际与版本有关 |
| `aim_speed` | `6.0` | 目标转速(Hz) |
| `sampling_rate` | `3` | 采样率档位 |
| `auto_reconnect` | `true` | 掉线自动重连 |
| `ignore_array_string` | `""` | 指定角度区间剔除（如门窗玻璃） |
| `inverted / reversion` | `false` | 安装方向/镜像修正 |
| `angle_offset` | `0.0` | 角度零位偏置 |

## 四、qpOASES —— 第三方库说明

- 开源二次规划(QP)求解器（POSIX/无 ROS 依赖），拥有 `include/qpOASES/*.hpp`、`examples/`、`doc/`；
- **本仓库学习路径中未参与编译**（无包级 CMake/package.xml 被上游引用），保留它是为后续算法（如碰撞避免中的优化问题）备用；
- 学习时可跳过，不影响主线。

## 五、与 originbot_base 的关系速记

```
originbot_base (./originbot_base)
   └─ find_package(serial) ───────────► serial_ros2（串口库）
vp100_ros2（雷达）  ──启用于────► originbot_bringup/vp100.launch.py
```

## 六、学习提示

1. `serial_ros2` 是 C++ 世界里典型的"COM 组件式"封装：公开 `Serial`/`Timeout` 两个类、隐藏平台上差异（unix.cc vs win.cc），达到"一处接入、处处可用"。
2. 雷达驱动的核心在 `nvilidar_process.cpp`：**协议解包 → 滤波 → 标准消息转换**，思路与 `originbot_base` 的 `processDataFrame` 完全同构，可对照学习。
3. 调试雷达：`ros2 topic echo /scan --once`（若数据流太大），或运行 `vp100_ros2_client` 看逐点数据。

## 七、速查表

- **serial_ros2**：库名 `serial`，默认 115200 8N1，API `setPort/read/write/open/close`；
- **vp100_ros2 启动**：`ros2 launch vp100_ros2 vp100_launch.py`；
- **vp100_ros2 话题**：`/scan (LaserScan)`；**TF**：`base_link→laser_link`；
- **串口**：`/dev/ttyUSB0` @ 230400（雷达）、`/dev/ttyS3` @ 115200（底盘）。