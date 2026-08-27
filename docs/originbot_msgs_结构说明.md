# originbot_msgs 功能包结构说明

> 学习用文档：帮助理解 OriginBot 自研消息/服务接口包。
> 代码位置：`originbot_msgs/`，全包 3 个 msg/srv 定义 + 构建配置，共几十行。
> 作用：供 `originbot_base`（C++）、`originbot_demo`（Python）等包**共享的接口类型契约**。

---

## 一、包的定位

ROS2 中节点间通信的消息类型必须**全工作区统一**。OriginBot 把底盘相关的私有接口抽取为独立包 `originbot_msgs`，避免不同包各自定义同名异义消息导致冲突。其他包通过 `find_package(originbot_msgs)` / `import originbot_msgs` 依赖它。

## 二、目录结构

```
originbot_msgs/
├── CMakeLists.txt        # rosidl_generate_interfaces 生成代码
├── package.xml
├── msg/
│   └── OriginbotStatus.msg   # 底盘状态消息
└── srv/
    ├── OriginbotBuzzer.srv   # 蜂鸣器控制服务
    ├── OriginbotLed.srv      # LED 控制服务
    └── OriginbotPID.srv      # 电机 PID 调参服务
```

## 三、接口定义详解

| 接口 | 类型 | 字段 | 生产者/消费者 |
|---|---|---|---|
| `OriginbotStatus` | msg | `float32 battery_voltage`、`bool buzzer_on`、`bool led_on` | 生产者 `originbot_base`（100ms 周期发布 `/originbot_status`）；消费者 `echo_status.py` 等 |
| `OriginbotBuzzer` | srv | 请求 `bool on` → 响应 `bool result` | 服务器 `originbot_base`；客户端 `control_buzzer.py` |
| `OriginbotLed` | srv | 请求 `bool on` → 响应 `bool result` | 服务器 `originbot_base`；客户端 `control_led.py` |
| `OriginbotPID` | srv | 请求 `float32 p/i/d` → 响应 `bool result` | 服务器 `originbot_base`（左/右轮两个服务）；供调参工具 |

### 消息文件内容

```
# msg/OriginbotStatus.msg
float32 battery_voltage
bool buzzer_on
bool led_on

# srv/OriginbotBuzzer.srv          # --- 上方为请求，下方为响应
bool on
---
bool result
```

## 四、构建与依赖

`CMakeLists.txt` 核心只有一段：

```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(originbot_msgs
  "msg/OriginbotStatus.msg"
  "srv/OriginbotBuzzer.srv"
  "srv/OriginbotLed.srv"
  "srv/OriginbotPID.srv")
```

- 构建类型：`ament_cmake` + `rosidl_default_generators`（自动为 C++/Python 生成代码）；
- 无任何运行依赖；是所有 package 的**叶节点**，被依赖方向单一（下游 → 它）。

## 五、学习提示

1. **改接口的连锁影响**：若修改字段，所有依赖包需重新编译。新增接口时在 `rti_` 目录（实际在此为 msg/srv 目录）加文件并在 CMakeLists 追加即可。
2. **用 `ros2 interface show` 快速查看**：`ros2 interface show originbot_msgs/srv/OriginbotPID`。
3. 它体现了 ROS2 `msg/srv` 定义独立成包的通用工程实践，学习时可对比 `nav_msgs`、`geometry_msgs` 等官方接口包的设计。