# originbot_base 功能包结构说明

> 学习用文档：帮助理解 OriginBot 底盘驱动包的整体结构与核心原理。
> 代码位置：`originbot_base/`，全包共 5 个源文件（头文件 180 行 + 主程序 839 行）。

---

## 一、包的定位

在 OriginBot 软件架构中，`originbot_base` 是**底盘驱动包**——它是 ROS2 上层应用（导航/遥控/深度学习）与底层硬件（含电机、编码器、IMU、LED、蜂鸣器的底盘板卡）之间的**桥梁**，通过**串口**通信，把 ROS 话题/服务翻译成底层板卡能理解的**自定义二进制协议帧**。

```
┌─────────────┐    话题/服务     ┌──────────────┐    UART 115200   ┌────────────────┐
│  上层应用     │ ──────────────► │ originbot_base │ ──────────────► │  底盘控制板     │
│ (导航/遥控等)  │                │   (本包)       │ ◄────────────── │  (电机/IMU/...) │
└─────────────┘                 └──────────────┘    数据帧(0x55)   └────────────────┘
```

## 二、目录结构

```
originbot_base/
├── CMakeLists.txt                       # 构建配置：依赖、可执行目标、安装规则
├── package.xml                          # 包元信息：名称/依赖/许可证
├── launch/robot.launch.py               # 启动文件：底盘节点 + 静态TF
├── include/originbot_base/
│   └── originbot_base.h                 # 头文件：所有结构体、枚举、类声明
└── src/
    └── originbot_base.cpp               # 主程序：全部实现 + main()
```

依赖关系（`CMakeLists.txt` / `package.xml`）：

| 依赖 | 用途 |
|---|---|
| `rclcpp` | ROS2 C++ 节点库 |
| `nav_msgs` | `/odom` 里程计消息 |
| `sensor_msgs` | `/imu` 惯性测量消息 |
| `geometry_msgs` | `/cmd_vel` 速度消息、TF |
| `serial` | 串口通信库 |
| `tf2_ros` | TF 广播 |
| `originbot_msgs` | 同仓库自研消息包（Status 消息 + Led/Buzzer/PID 服务） |

## 三、核心设计：一个类、两个线程

所有逻辑都封装在 `OriginbotBase` 类（继承 `rclcpp::Node`，节点名 `originbot_base`）中：

```
┌── OriginbotBase (rclcpp::Node) ────────────────────────────────────────┐
│                                                                        │
│  线程① 主线程 (rclcpp::spin)                线程② 读串口线程             │
│  ├─ 订阅回调  /cmd_vel        ──► 发速度帧   └─ readRawData() 逐字节扫描   │
│  ├─ 服务回调  led / buzzer                 ├─ 找帧头 0x55               │
│  │           left_pid / right_pid          ├─ 校验和检查                │
│  ├─ 定时器    100ms 自动停车 + 发状态        └─ 按帧ID分发处理            │
│  └─ 发布者    /odom /imu /originbot_status                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.1 类的成员函数划分（按职责分 5 组）

| 分组 | 函数 | 作用 |
|---|---|---|
| **串口解析层** | `readRawData()` `checkDataFrame()` `processDataFrame()` | 读帧 → 校验帧头/校验和/帧尾 → 按 ID 分发给处理函数 |
| **数据解析层**（上行） | `processVelocityData()` `processAccelerationData()` `processAngularData()` `processEulerData()` `processSensorData()` | 把 6 字节 payload 解析成轮速 / 加速度 / 角速度 / 欧拉角 / 电池电压 |
| **数据处理层** | `imu_conversion()` `imu_calibration()` `degToRad()` `odom_publisher()` `imu_publisher()` | 单位换算、里程计积分、IMU 校准 |
| **控制层**（下行） | `cmd_vel_callback()` `buzzer_control()` `led_control()` 及三个服务的回调 | 把 ROS 指令封装成数据帧写串口 |
| **维护层** | `timer_100ms_callback()` | 自动停车(看门狗) + 周期发布机器人状态 |

### 3.2 关键成员变量

```cpp
constexpr ORIGINBOT_WHEEL_TRACK = 0.11;   // 轮距 0.11m，差速运动学核心参数
serial::Serial serial_;                   // 串口对象（/dev/ttyS3, 115200）
float odom_x_, odom_y_, odom_th_;         // 里程计三要素（死区累积，不依赖外部）
DataImu imu_data_;  RobotStatus robot_status_;      // 状态缓存
correct_factor_vx_/vth_                   // 速度校正系数（轮径/轮距误差补偿）
auto_stop_on_/auto_stop_count_            // 自动停车看门狗
```

### 3.3 头文件中的关键类型定义

```cpp
#define ORIGINBOT_WHEEL_TRACK (0.11)      // 轮距 0.11 米

typedef struct {                          // 串口协议帧，共 11 字节
    uint8_t header;                       // 帧头 0x55
    uint8_t id;                           // 帧 ID（区分数据类型）
    uint8_t length;                       // payload 长度，固定 0x06
    uint8_t data[6];                      // 6 字节数据
    uint8_t check;                        // 校验和 = sum(data) & 0xFF
    uint8_t tail;                         // 帧尾 0xBB
} DataFrame;

typedef struct {                          // IMU 数据结构体
    float acceleration_x/y/z;             // 三轴加速度 (m/s^2)
    float angular_x/y/z;                  // 三轴角速度 (rad/s)
    float roll, pitch, yaw;               // 三轴姿态角 (rad)
} DataImu;

typedef struct {                          // 机器人状态结构体
    float battery_voltage;                // 电池电压 (V)
    bool buzzer_on;                       // 蜂鸣器状态
    bool led_on;                          // LED 状态
} RobotStatus;
```

## 四、串口通信协议（理解本包最关键的部分）

### 4.1 帧格式（小端）

```
┌────────┬──────┬────────┬──────────────┬───────┬──────┐
│ header │ id   │ length │ data[0..5]   │ check │ tail │
│  0x55  │ 帧ID │  0x06  │ 6字节Payload │ 校验和 │ 0xBB │
└────────┴──────┴────────┴──────────────┴───────┴──────┘
check = (data[0]+..+data[5]) & 0xFF     // 简单取和校验
```

2 字节数值统一采用：**低字节在前，高字节在后**。
例如轮速左轮 `data[1]=val & 0xFF`，`data[2]=(val>>8) & 0xFF`。

### 4.2 帧 ID 含义与方向

| 帧ID | 含义 | 方向 | 触发方式 |
|---|---|---|---|
| 0x01 | 速度指令 (左右轮 mm/s + 符号位) | 下行 | `/cmd_vel` 或自动停车 |
| 0x02 | 轮速反馈 (差速 → vx/vth) | 上行 | 板卡上报 |
| 0x03 | IMU 加速度 (±16g, ×9.8 换算 m/s²) | 上行 | 板卡上报 |
| 0x04 | IMU 角速度 (±2000°/s) | 上行 | 板卡上报 |
| 0x05 | IMU 欧拉角 (±180°) | 上行 | 板卡上报 |
| 0x06 | 传感器 (电池电压) | 上行 | 板卡上报 |
| 0x07 | HMI (LED、蜂鸣器) / IMU 校准 | 下行 | 服务调用/开机校准 |
| 0x08 | 左轮 PID 参数 | 下行 | 服务调用 |
| 0x09 | 右轮 PID 参数 | 下行 | 服务调用 |

> **速度数据编码细节**（下行 0x01 帧）：`data[0]`（左轮）和 `data[3]`（右轮）是方向符号位（`0x00`=反向，`0xFF`=正向），后两位为速度绝对值的低/高字节，单位 mm/s。
> **上行 0x02 帧**则相反：`data[0]`(`data[3]`) 为 `0` 表示反向，`1` 表示正向，且低字节在前。

### 4.3 上行数据中的单位换算参考

| 数据类型 | 原始对应 | 换算公式 | 结果 |
|---|---|---|---|
| 轮速 | mm/s，int16 | `speed/1000`，符号由 data[0]/data[3] 决定 | m/s |
| 加速度 | ±32768 对应 ±16g | `val/32768 * 16 * 9.8` | m/s² |
| 角速度 | ±32768 对应 ±2000°/s | `val/32768 * degToRad(2000)` | rad/s |
| 欧拉角 | ±32768 对应 ±180° | `val/32768 * degToRad(180)` | rad |
| 电池电压 | data[0] 整数部分, data[1] 小数部分 | `data[0] + data[1]/100.0` | V |

## 五、ROS2 接口清单

| 类型 | 名称 | 消息/服务 | 方向 |
|---|---|---|---|
| 订阅 | `/cmd_vel` | `geometry_msgs/Twist` | 输入 |
| 发布 | `/odom` | `nav_msgs/Odometry` | 输出 |
| 发布 | `/originbot_status` | `originbot_msgs/OriginbotStatus` (电压/LED/蜂鸣器) | 输出 |
| 发布 | `/imu` (可选) | `sensor_msgs/Imu` | 输出 |
| 服务 | `/originbot_led` | `OriginbotLed` (bool on → bool result) | 输入 |
| 服务 | `/originbot_buzzer` | `OriginbotBuzzer` (bool on → bool result) | 输入 |
| 服务 | `/originbot_left_pid` | `OriginbotPID` (float32 p/i/d → bool result) | 输入 |
| 服务 | `/originbot_right_pid` | `OriginbotPID` (float32 p/i/d → bool result) | 输入 |
| TF | `odom → base_footprint` (动态, 由里程计划算) | | 输出 |
| TF | `base_footprint → base_link` (静态, z=0.05325m) | | 静态 |
| TF | `base_link → imu_link` (静态, 零偏移) | | 静态 |
## 六、核心数据流（两条主链路）

**链路① 控制（下行）**：`/cmd_vel` (vx, ω)
→ **差速运动学逆解**：`left = vx - ω·track/2`，`right = vx + ω·track/2`
→ m/s → mm/s + 方向符号位 → 封装 0x01 帧 → 串口写入

**链路② 里程反馈（上行）**：0x02 帧
→ **差速运动学正解**：`vx = k_vx·(left+right)/2`，`vth = k_vth·(right-left)/track`
→ **航位推算（积分叠加）**：`Δx=vx·cos(θ)·dt`，`Δy=vx·sin(θ)·dt`，`Δθ=vth·dt`
→ 角度归一化到 [-π, π]
→ 发布 `/odom`（分静止/运动两套协方差矩阵）+ 广播 `odom→base_footprint` TF

## 七、launch 文件解析（`robot.launch.py`）

| 参数 | 默认值 | 作用 |
|---|---|---|
| `port_name` | `ttyS3` | 串口设备名（代码自动加 `/dev/` 前缀） |
| `correct_factor_vx` | `0.898` | 线速度校正系数 |
| `correct_factor_vth` | `0.874` | 角速度校正系数 |
| `auto_stop_on` | `true` | 0.5s 收不到指令自动停车 |
| `use_imu` | `false` | 是否采集并发布 IMU 数据 |
| `pub_odom` | `true` | 是否由本节点发布 odom TF |

启动的 3 个节点：

1. `originbot_base`（本包底盘驱动，reading 串口 + spin 回调）
2. `tf2_ros/static_transform_publisher`：`base_footprint → base_link`（z=0.05325m）
3. `tf2_ros/static_transform_publisher`：`base_link → imu_link`（零偏移）

通常由 `originbot_bringup/originbot.launch.py` 通过 `IncludeLaunchDescription` 包含启动。

## 八、容易被忽略的设计细节（学习重点）

1. **自动停车看门狗**：收到新 `cmd_vel` 就把 `auto_stop_count_` 清零；100ms 定时器里计数，累计超过 5 次（约 0.5s）没新指令就发 0x01 零速帧强制刹车。这是**安全机制**，避免节点崩溃时小车失控；计数置 255 是为了保持"已停车"语义。
2. **IMU 开机校准**：若 `use_imu=true`，构造函数中先发 0x07 帧（`data[4]=0xFF, data[5]=0xFF`）触发板卡静态校准，再 `usleep(500ms)` 等待完成。
3. **启动自检提示**：初始化完成后蜂鸣器响 0.5s 再关闭，表示节点正常启动。
4. **退出保护**：`sigintHandler` 捕获 SIGINT 后，**新建一个独立串口**发零速帧（此时原串口可能已在析构中），再 `rclcpp::shutdown()`，保证断电前小车刹停。
5. **里程计误差来源**：轮距为常量 0.11m，轮子打滑或轮径偏差会造成积分漂移，这就是 `correct_factor` 校正参数存在的意义；且里程计产生于驱动节点，不同包之间不能直接复用。
6. **协方差切换**：静止（vx==vth==0）时发布的 odom 用更小的不确定性矩阵，辅助导航算法判断"确实没动"（如避免`cmd_vel`下车还在缓慢积分的现象）。
7. **线程不共享锁**：串口写只发生在主线程（回调/定时器），读只发生在读线程，因此无需加锁；这也是该实现能在如此精简的代码量下保持稳定的原因。

## 九、建议的学习路径

1. **先跑通、再看代码**：`ros2 launch originbot_base robot.launch.py` 启动后，
   `ros2 topic echo /odom` 看里程、`ros2 run teleop_twist_keyboard teleop_twist_keyboard` 遥控小车、`ros2 service call /originbot_led originbot_msgs/srv/OriginbotLed "{on: true}"` 点亮 LED。
2. **逆向阅读源码**：从 `main()`（824 行）起步 → 构造函数（参数/串口/接口创建）→ `readRawData()`（读线程）→ `processDataFrame()`（分发）→ 各 `process*Data()`（解析）→ `odom_publisher()`（发布），整体是一条可循的单向链。
3. **抓原帧调试**：打开 `readRawData()` 中被注释的 `printf("Frame raw data...")`，对照 4.1 的帧格式手动解析一帧，理解协议最直观。
4. **动手改一改**：
   - 把 `ORIGINBOT_WHEEL_TRACK` 换成实测轮距，观察里程精度变化；
   - 新增一种 `FRAME_ID_*` 帧类型，完整走一遍「串口协议定义 → 解析函数 → 话题发布 → RViz2 查看」的链路；
   - 写一个 `ros2 service` 调用 `OriginbotPID` 服务，调节电机 PID 再实测响应。
5. **串联整个工作区**：结合 `originbot_bringup`（整机启动）、`originbot_navigation`（导航消费 odom/cmd_vel）、`originbot_demo`（遥控/寻线）阅读各包对 `/cmd_vel` 与 `/odom` 的依赖，就能理解本包在整机中的枢纽地位。

## 十、速查表

- **启动**：`ros2 launch originbot_base robot.launch.py`
- **监听串口**：`/dev/ttyS3` @ 115200, 8N1
- **核心话题**：订阅 `/cmd_vel`，发布 `/odom` `/originbot_status` `/imu(可选)`
- **核心服务**：`originbot_led` `originbot_buzzer` `originbot_left/right_pid`
- **关键常量**：轮距 `0.11m`、静态TF高度 `0.05325m`、波特率 `115200`、帧头 `0x55` 帧尾 `0xBB`