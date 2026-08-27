# originbot_demo 功能包结构说明

> 学习用文档：帮助理解 OriginBot 的 Python 入门示例集合。
> 代码位置：`originbot_demo/`，**纯 ament_python 包**，7 个独立脚本 + 测试。
> 每个脚本都是"怎么用 ROS2 接口"的最小可运行范例，适合作为 Python 端的第一份参考。

---

## 一、包的定位

演示如何与底盘驱动 `originbot_base` 交互：订阅话题、调用服务、发布速度指令。代码注释详尽、逻辑极简，是**ROS2 通信机制实验场**。

## 二、目录结构

```
originbot_demo/
├── setup.py / setup.cfg / package.xml
├── originbot_demo/
│   ├── __init__.py
│   ├── control_led.py        # 服务客户端：控制 LED 开关
│   ├── control_buzzer.py     # 服务客户端：控制蜂鸣器
│   ├── draw_circle.py        # 话题发布：画圆运动
│   ├── echo_odom.py          # 话题订阅：打印里程计
│   ├── echo_status.py        # 话题订阅：打印底盘状态
│   ├── take_pictures.py      # 相机：定时拍照保存 jpg
│   └── transport_img.py      # 图像压缩转发（编码+解码回发）
└── test/                     # pytest 风格空测试（copyright/flake8/pep257）
```

## 三、脚本逐一说明

| 脚本 | 通信方式 | 关键接口 | 演示要点 |
|---|---|---|---|
| `control_led.py` | 服务**客户端** | `originbot_msgs/srv/OriginbotLed` → `/originbot_led` | `create_client` + `wait_for_service` + `call_async`，每 3s 翻转 LED |
| `control_buzzer.py` | 服务客户端 | `OriginbotBuzzer` → `/originbot_buzzer` | 同上，操控蜂鸣器 |
| `draw_circle.py` | 话题**发布者** | `geometry_msgs/Twist` → `/cmd_vel` | `create_publisher` + `create_timer(0.5s)`，周期发布 vx/ω 形成圆周运动 |
| `echo_odom.py` | 话题订阅者 | `nav_msgs/Odometry` ← `/odom` | `create_subscription` 回调打印位姿 |
| `echo_status.py` | 话题订阅者 | `OriginbotStatus` ← `/originbot_status` | 打印电压/LED/蜂鸣器状态 |
| `take_pictures.py` | 图像订阅 | `sensor_msgs/Image` ← `/image` | `CvBridge` 转换 → OpenCV 定时存 jpg |
| `transport_img.py` | 图像转码转发 | Image ← `/image` → `CompressedImage` + `bgr8_image` | `cv2.imencode(JPEG质量50)` 压缩再解码输出，理解图像传输 |

### 典型模式速写（服务客户端，control_led.py 骨架）

```python
import rclpy
from rclpy.node import Node
from originbot_msgs.srv import OriginbotLed

class serverClient(Node):
    def __init__(self, name):
        super().__init__(name)
        self.client = self.create_client(OriginbotLed, 'originbot_led')
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.request = OriginbotLed.Request()

    def send_request(self, led_on):
        self.request.on = led_on
        self.future = self.client.call_async(self.request)

def main(args=None):
    rclpy.init(args=args)
    node = serverClient("control_led")
    led_on = True
    while rclpy.ok():
        node.send_request(led_on)
        rclpy.spin_once(node)      # 非阻塞处理异步结果
        led_on = not led_on
        time.sleep(3)
    ...
```

## 四、学习提示

1. **三件套背诵**：ROS2 Python 节点 = `Node` 子类 + `rclpy.spin*`(或 `spin_once` 手写循环) + 通信对象；此包 7 个脚本把话题(收/发)、服务(收/发可扩展)、图像全演了一遍；
2. `control_led.py` 与 `control_buzzer.py` 结构**一模一样**，只差服务类型与话题名——理解一个即通两个；
3. `transport_img.py` 是最贴近真实应用的样例：CvBridge、JPEG 压缩、双话题发布，可复用作"图传压缩节点"的起点；
4. 运行前提：底盘节点已启动（`ros2 launch originbot_base robot.launch.py`）。

## 五、速查表

| 命令 | 效果 |
|---|---|
| `ros2 run originbot_demo draw_circle` | 小车画圆周 |
| `ros2 run originbot_demo echo_odom` | 打印里程 |
| `ros2 run originbot_demo control_led` | 每 3s 翻转 LED |
| `ros2 run originbot_demo take_pictures` | 定时拍照到当前目录 |

## 六、延伸

与 `originbot_example`（C++ 三个实例）呼应：本包是 **Python 版最小集**，两者任务互补——CLI 服务/话题用 Python 更短，Action 客户端与键盘操控用 C++ 示例更完整。