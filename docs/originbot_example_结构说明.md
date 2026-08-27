# originbot_example 功能包结构说明

> 学习用文档：帮助理解 OriginBot 的三个 C++ 实战示例。
> 代码位置：`originbot_example/`，内含 **3 个独立 ament_cmake 子包**（无聚合 CMake，各自独立构建）。

---

## 一、包的定位

提供"开箱即玩"的三类实验：

| 子包 | 功能 | 用到的 ROS2 机制 |
|---|---|---|
| `originbot_teleop` | 键盘遥控小车 | 发布 `/cmd_vel` + 终端非缓存键盘读取 |
| `originbot_send_goal` | 给 Nav2 发送导航目标 | **Action 客户端**（`navigate_to_pose`） |
| `originbot_qrcode_detect` | 二维码识别并驱动小车 | 话题订阅 + 视觉处理（zbar）+ `/cmd_vel` |

## 二、originbot_teleop —— 键盘遥控

### 结构

```
originbot_teleop/
├── include/originbot_teleop.hpp    # 类"OriginbotTeleop"(继承 Node)
└── src/originbot_teleop.cc         # 实现 + main
```

### 核心逻辑

```
构造函数：
 1 设置终端的非缓存模式(tcsetattr, 去掉 ICANON|ECHO)   ← 不需要回车就能读单个按键
 2 create_publisher<Twist>("cmd_vel", 1)                ← 输出
 3 showMenu() 打印按键说明
 4 teleopKeyboardLoop()：poll() 500ms 超时轮询键盘
    ├─ i/k 加速/减速(线性), j/l 加减角速度
    └─ 发布对应 Twist → /cmd_vel
析构：恢复终端原始设置(tcsetattr restore)
```

- 按键布局：`w=前进, s=后退, a/d=原地左右转, q/e=左前/右前, z/c=左后/右后`；
- **仿 telegram 中断点**：用 `boost::this_thread::interruption_point()` 每轮检查线程中断——这是 ROS1 时代的旧代码风格遗留，学习时可忽略；
- 默认最大速度由宏定义（头文件 `MAX_SPEED_LINEARE_X` / `MAX_SPEED_ANGULAR_Z`）。

## 三、originbot_send_goal —— Nav2 目标点发送

### 结构

```
originbot_send_goal/
└── src/send_goal_node.cpp    # 单一文件，类 GoalCoordinate
```

### 核心逻辑（Action 客户端的标准六步）

```cpp
using NavigateToPose = nav2_msgs::action::NavigateToPose;
1. rclcpp_action::create_client<NavigateToPose>(this, "navigate_to_pose");
2. wait_for_action_server();                    // 等待 Nav2 服务端
3. 构造 Goal(pose.header.frame_id="map"; x=1, y=1, yaw=0);
4. 注册三个回调：goal_response / feedback / result；
5. async_send_goal(...)                         // 异步发送
6. feedback 回调打印 distance_remaining 剩余距离
```

- **关键学习点**：Action 与 Topic/Service 三者在接口语义上的对比——长任务、可取消、带反馈，正是 Action 的用武之地；
- 目标值是写死的 `(1.0, 1.0)`，学习时可改为通过 launch 参数/cmdline 传入。

## 四、originbot_qrcode_detect —— 二维码控制

### 结构

```
originbot_qrcode_detect/
├── src/
│   ├── qrcode_control.cpp    # 控制节点：订阅二维码信息 → 发 /cmd_vel
│   └── qr_decoder.cpp        # 解码节点：图像→zbar 解析→发出结果
└── launch/qrcode_control.launch.py   # 同时启动两个节点
```

### 数据流

```
/image →(qr_decoder: zbar 扫码)
   ├── /qr_code_result (std_msgs/String, 内容码)
   ├── /qrcode_detected/pose_result (geometry_msgs/Pose, 位置)
   └── 供 QrCodeControl 消费 →
        根据"位置误差 + 内容码"组合 → 发布 /cmd_vel → 底盘运动
```

### 控制策略（qrcode_control.cpp 要点）

```cpp
#define X_CENTER_MAX(380) / MIN(270)   // 画面中心 x 阈值
#define Z_SIZE_MAX / MIN               // 二维码尺寸阈值(远/近判断)
若 qr 在画面中央且尺寸合适 → 读取码值执行动作
   (如: 转弯/前进/保持, 值不同动作不同)
否则 → 停车
```

- 这是"**视觉伺服(visual servoing)**"思想的一个玩具实现：用目标在画面中的**位置误差**直接转成底盘速度；
- 阈值宏集中在文件头，方便按摄像头分辨率调参。

## 五、包间依赖速查

| 子包 | 依赖外部包 | 消费话题/动作 | 输出话题 |
|---|---|---|---|
| originbot_teleop | geometry_msgs | - | `/cmd_vel` |
| originbot_send_goal | nav2_msgs, rclcpp_action | `/navigate_to_pose` (Action) | - |
| originbot_qrcode_detect | zbar、OpenCV、std_msgs | `/image`(由 qr_decoder 接相机) | `/cmd_vel`、`/qr_code_result` |

## 六、学习提示

1. 三个示例分别覆盖 **发布者 / Action 客户端 / 视觉控制**，是 C++ 端从"会发"到"实用"的进阶路径；
2. `originbot_teleop` 的终端**原始模式**处理（`tcgetattr`/`tcsetattr`）是 Linux 终端编程的经典知识，与 ROS 无直接关系；
3. 对照 `originbot_demo`（Python）看同一类任务在不同语言下的写法规约差异；
4. 跑 `send_goal` 前必须先启动导航：`ros2 launch originbot_navigation nav_bringup.launch.py`。

## 七、速查表

| 命令 | 说明 |
|---|---|
| `ros2 run originbot_teleop originbot_teleop` | 键盘遥控 |
| `ros2 run originbot_send_goal send_goal_node` | 发送(1,1)目标点 |
| `ros2 launch originbot_qrcode_detect qrcode_control.launch.py` | 二维码循控制 |
| `ros2 topic echo /qr_code_result` | 查看识别码值 |