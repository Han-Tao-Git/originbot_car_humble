# originbot_bringup 功能包结构说明

> 学习用文档：帮助理解 OriginBot 整机一键启动的编排逻辑。
> 代码位置：`originbot_bringup/`，全包无 C++/Python 业务代码，纯 **launch 编排 + 参数配置**。

---

## 一、包的定位

`originbot_bringup` 是 OriginBot 的**总电源开关**：一个 `originbot.launch.py` 按条件组合启动底盘、雷达、相机等子系统，并提供手柄遥控、相机查看等周边 launch。

## 二、目录结构

```
originbot_bringup/
├── CMakeLists.txt
├── package.xml
├── launch/
│   ├── originbot.launch.py            # ★ 整机总启动入口
│   ├── vp100.launch.py                # 激光雷达（复用 originbot_driver/vp100_ros2 的 launch）
│   ├── camera.launch.py               # USB 相机（hobot_shm + hobot_usb_cam + hobot_codec）
│   ├── camera_internal.launch.py      # 相机(内参标定文件版本)
│   ├── camera_websoket_display.launch.py  # 相机 + 人体检测 + WebSocket 远程显示
│   └── joy_teleop.launch.py           # 手柄遥控
├── config/joy.yaml                    # 手柄按钮/轴映射
└── param/ydlidar.yaml                 # YDLidar 雷达备选参数
```

## 三、总启动入口 `originbot.launch.py`

### 可传参数

| 参数 | 默认值 | 作用 |
|---|---|---|
| `use_lidar` | `false` | 是否包含 `vp100.launch.py` |
| `use_camera` | `false` | 是否包含 `camera.launch.py` |
| `use_imu` | `false` | 透传给底盘 `robot.launch.py`（IMU 开关） |
| `pub_odom` | `true` | 透传给底盘（是否发布 odom TF） |

### 逻辑结构（全部走 `IncludeLaunchDescription` 组合）

```
originbot.launch.py
 ├── Include originbot_base/robot.launch.py      # ★ 底盘节点（必启动）
 │       └─ 透传 use_imu / pub_odom
 ├── [use_lidar]  Include vp100.launch.py        # 雷达
 └── [use_camera] Include camera.launch.py       # 相机
```

> **设计亮点**：它不重新实现节点，而全部通过 `python launch 嵌套包含`。这正是 ROS2 launch 的**复用与分层**思想——各部门把 launch 写在自己包里，总入口只做"编排"。

## 四、相机链路 `camera.launch.py`

出图链路为三段式（这也是 Horizon RDK 相机的常见组合）：

```
hobot_shm（共享内存传输）→ hobot_usb_cam（mjpeg 采集 /dev/videoX, zero_copy）
   → hobot_codec_republish（硬件解码）
   → /image  (sensor_msgs/Image, bgr8)
```

- 参数通过 `-p` 内联传参（代码注释明确说明：params 文件方式会导致 `hobot_usb_cam` 无法识别 `video_device` 而逐个探测 `/dev/video0..8` 崩溃）；
- `camera_internal.launch.py` 额外传入标定文件 `usb_camera_calibration.yaml`；
- `camera_websoket_display.launch.py` 追加 `mono2d_body_detection`（人体检测）并接 WebSocket 图传，供网页端看画面。

## 五、手柄遥控 `joy_teleop.launch.py` + `config/joy.yaml`

- 子系统：`joy_linux`（读手柄） + `teleop_twist_joy`（按映射发布 `/cmd_vel`）；
- 按键映射（XBox 布局）：
  - **左摇杆**：上下 = 前进/后退（线性），左右 = 转向（角速度）；
  - **L1 (button 4)** = 使能；**R1 (button 5)** = 涡轮加速（Turbo）；
- 速度档位：

| 档 | 线速度 x | 角速度 yaw |
|---|---|---|
| 正常 | 0.2 m/s | 0.5 rad/s |
| Turbo | 0.5 m/s | 1.9 rad/s |

```
joy_linux(硬件驱动)
   → /joy (sensor_msgs/Joy)
   → teleop_twist_joy(读 joy.yaml 映射)
   → /cmd_vel → 底盘
```

## 六、备选雷达参数 `param/ydlidar.yaml`

- 面向 YDLidar（与 VP100 不同品牌）备用：`port=/dev/ydlidar`, `baudrate=115200`, `frame_id=laser_link`, 8Hz, 0.01~12m 量程；
- 说明本仓库雷达存在 **VP100 + YDLidar 两套方案**，启动时按硬件选择。

## 七、学习提示

1. **launch 三要素**：`DeclareLaunchArgument`（声明）、`LaunchConfiguration`（取值）、`IncludeLaunchDescription`（引用），熟悉这三者即可读懂全部 launch；
2. 对比 `robot.launch.py`（底盘包内部自启动静态 TF）与 `originbot.launch.py`（全局编排）的职责边界；
3. 家用/教学场景的"一键启动"就是这样逐层 include 组合的，可尝试在 `originbot.launch.py` 中自加一个 `use_xxx` 参数包含新功能。

## 八、速查表

- **整机启动**：`ros2 launch originbot_bringup originbot.launch.py use_lidar:=true use_camera:=true`
- **手柄**：`ros2 launch originbot_bringup joy_teleop.launch.py`
- **相机**：`ros2 launch originbot_bringup camera.launch.py`
- **出图话题**：`/image (bgr8)`；**手柄话题**：`/joy` → `/cmd_vel`。