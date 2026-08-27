# originbot_linefollower 功能包结构说明

> 学习用文档：帮助理解 OriginBot 的经典视觉循迹实现。
> 代码位置：`originbot_linefollower/`，**Python ament_python 包**，核心只有一个 `follower.py`，约百行。
> 算法本质：基于颜色分割的**单点重心跟踪 + P 控制器**——计算机视觉入门最经典的教学案例。

---

## 一、包的定位

让小车沿着地面**黄色胶带线**自动行驶：订阅相机图像 → 提取黄色线条 → 计算其中心与画面中心偏差 → 发布 `/cmd_vel` 纠偏。

## 二、目录结构

```
originbot_linefollower/
├── setup.py / setup.cfg / package.xml
├── originbot_linefollower/
│   ├── __init__.py
│   └── follower.py        # ★ 全部逻辑
└── test/                  # 标准 pytest 空测试
```

## 三、follower.py 逐段解析

```python
class Follower(Node):
    def __init__(self):
        super().__init__('line_follower')
        self.bridge = cv_bridge.CvBridge()
        self.image_sub = self.create_subscription(Image, '/image', self.image_callback, 10)
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.pub = self.create_publisher(Image, '/camera/process_image', 10)  # 调试用
```

### 处理管线（image_callback 内）

```
Step1  图像转换     : CvBridge imgmsg_to_cv2(msg, 'bgr8')
Step2  颜色分割     : BGR→HSV，用 inRange 提取黄色 (H∈[10,255], S≥70, V≥30) → mask
Step3  关注区域(ROI): 只保留画面中下部 [h/2, h/2+20] 的横向条带
                     （屏蔽远处景物与近处地面干扰）
Step4  重心计算     : cv2.moments(mask) → m00=m00>0 时 cx=m10/m00
Step5  偏差控制     : err = cx - w/2 (线与画面中心的横向偏差)
                     vx = 0.1 m/s（恒速前进）
                     ω  = -err/400（比例纠偏，P 控制）
Step6  发布         : cmd_vel_pub.publish(twist)
                     同时 publish 标注圆圈后的图像到 /camera/process_image（可视化）
```

## 四、三个值得学习的工程细节

1. **HSV颜色空间比 BGR 更稳**：光照变化下色调(H)相对稳定，`lower/upper_yellow` 用 HSV 阈值比 RGB 阈值鲁棒；
2. **ROI 裁剪**：只在前视近处的窄条带中找线，从根源上滤除天花板/远处杂色——"**先减负再识别**"是感知前处理通用心法；
3. **P 控制一行完成**：`angular.z = -float(err)/400`，无需 PID 库，纯比例控制对"循高速线"足够。比例系数 400 是经验值，画面分辨率变时必须重调。

## 五、运行与依赖

- **必需**：相机已启动并发布 `/image (bgr8)`（`ros2 launch originbot_bringup originbot.launch.py use_camera:=true`）+ 底盘节点已启动；
- 运行：`ros2 run originbot_linefollower follower`；
- 依赖（Python）：`rclpy`、`cv_bridge`、`opencv(cv2)`、`numpy`、`sensor_msgs`、`geometry_msgs`；
- 调试：`ros2 run rqt_image_view rqt_image_view` 看 `/camera/process_image`（已画圆圈标注）。

## 六、学习提示

1. 这是"**图像 → 单点误差 → 速度指令**"的极简闭环，与 `originbot_example/qrcode_control` 的视觉伺服思想同根；
2. 可与深度学习版 `originbot_deeplearning/line_follower_perception`（ResNet18 分割）对比：经典 CV 与深度网络处理同一任务时在鲁棒性/算力上的权衡；
3. 关于"线在前面左/右偏多少该转多大角"的比例系数，可动手把 400 改 200/800 观察震荡与响应——这是体验控制论"增益过大振荡"最直观的实验。

## 七、速查表

- **启动**：`ros2 run originbot_linefollower follower`
- **输入**：`/image`；**输出**：`/cmd_vel`、`/camera/process_image`
- **可调量**：黄色阈值（`lower/upper_yellow`）、ROI 行区间、恒速 `0.1`、P 系数 `400`