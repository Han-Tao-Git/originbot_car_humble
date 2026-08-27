# originbot_deeplearning 功能包结构说明

> 学习用文档：帮助理解 OriginBot 的 AI+导航套件。
> 代码位置：`originbot_deeplearning/`，内含 **3 个相互独立的子包**，基于地平线 RDK 平台（TROS / dnn_node）实现视觉 AI 应用。
> 说明：本套件面向 `d-robotics` 的 `tros` 运行环境，代码风格与主线 ROS2 手册差异较大（大量使用 `hbm_img_msgs` 共享内存零拷贝、`ai_msgs`）。

---

## 一、包的定位

把"视觉感知 → 运动决策"做成可直接部署的三大应用：

| 子包 | 功能 | 输出控制 |
|---|---|---|
| `body_tracking` | 人体检测与跟随 | 跟随目标 → `/cmd_vel` |
| `gesture_control` | 手势识别（666/Yeah/拇指左/右） | 前进/后退/左转/右转 → `/cmd_vel` |
| `line_follower_perception` | 深度学习线识别（ResNet18, NV12） | 发布线偏差（供循迹） |

三个包均消费相机 `/image`（或共享内存），产出 `/cmd_vel` 驱动 `originbot_base` 底盘。

## 二、body_tracking —— 人体跟随

### 目录（约 1041 行核心算法）

```
body_tracking/
├── include/
│   ├── body_tracking.h        # 算法引擎：目标锁定/丢判/速度决策
│   ├── smart_subscriber.h     # 异步订阅封装
│   ├── robot_ctrl_node.h      # 控制节点：读引擎决策 → /cmd_vel
│   ├── param_node.h          # 参数节点
│   └── util.h / time_helper.h / common.h
├── src/body_tracking.cpp  main.cpp  smart_subscriber.cpp  util.cpp
└── launch/body_tracking*.launch.py   (3 种变体组合)
```

### 数据流

```
/hbmem_img(共享内存) → mono2d_body_detection(人体检测, TROS 节点)
   → /hobot_mono2d_body_detection (ai_msgs/PerceptionTargets)
   → 本包 body_tracking（锁定目标: 距离/横向偏差 → 速度决策）
   → /cmd_vel → 底盘
```

### 决策要点（body_tracking.cpp）

- 用**卡尔曼滤波/几何关系**保持目标锁定，设置"丢失判定"超时与重新捕获逻辑；
- 速度输出按偏差分档（线性 + 角速度），实现平滑跟随；
- launch 有 `body_tracking`、`body_tracking_without_gesture`、
  `body_tracking_without_input_node` 三种变体，分别适配"带手势/不带手势/直连输入"场景。

## 三、gesture_control —— 手势控制

### 手势映射

| 手势 | 动作 |
|---|---|
| 666 / Awesome | 前进 |
| Yeah / Victory | 后退 |
| 大拇指向右 | 右转 |
| 大拇指向左 | 左转 |

### 结构

```
gesture_control/
├── include/{common.h, gesture_control_engine.h, gesture_control_node.h, param_node.h}
├── src/{gesture_control_engine.cpp, gesture_control_node.cpp, param_node.cpp, main.cpp}
└── launch/gesture_control.launch.py
```

- `gesture_control_engine`：手势分类器接口（对接 `hand_gesture_detection` TROS 节点）；
- `gesture_control_node`：把手势类别映射为 Twist 速度指令（定时/持续输出，带刹车）；
- `param_node`：负责读取/广播运行参数。

## 四、line_follower_perception —— AI 循迹感知

```
line_follower_perception/
├── include/line_follower_perception/line_follower_perception.h
├── src/line_follower_perception.cpp   (281 行)
├── model/resnet18_224x224_nv12.bin   # 预训练模型（NV12 输入）
└── 依赖: dnn_node, hbm_img_msgs, ai_msgs, geometry_msgs
```

- 使用地平线 `dnn_node` 推理 ResNet18 分割线场景，输出**线的横向偏差/方向**（`ai_msgs`），替代经典 CV 的 HSV 方法（对比 `originbot_linefollower`）；
- 流程：`/image → 模型推理(token/语义分割) → 计算偏差 → 发布` 供循迹控制器消费。

## 五、与整体架构的关系

```
┌─ originbot_deeplearning ─────────────────────────────┐
│ body_tracking ──┐                                    │
│ gesture_control ─┼──► /cmd_vel ──► originbot_base     │
│ line_follower_perception ─► 偏差话题                   │
└───────────────────▲──────────────────────────────────┘
                    └── /image(相机, 经 hobot_* 编码链)
```

## 六、学习提示

1. **面向 RDK 平台**：编译需 `tros`/`dnn_node` 等商业/专用二进制包，普通 PC 上无法直接编译运行，阅读源码应聚焦**决策算法**（目标锁定、手势映射）而非底层封装；
2. **接口差异**：NDK 链路使用 `hbm_img_msgs`（共享内存零拷贝）与 `ai_msgs`（感知结果），与主线 `sensor_msgs` 生态不同——这本质是"**大消息走共享内存**"的工程选型；
3. 三个包分别示范三类经典范式：跟踪、分类控制、分割感知，可与经典算法版对照（`originbot_linefollower` vs `line_follower_perception`）。

## 七、速查表

| 包 | 模型/算法 | 输入 | 输出 |
|---|---|---|---|
| body_tracking | mono2d 人体检测 + 跟踪 | `/image`/`hbmem_img` | `/cmd_vel` |
| gesture_control | hand_gesture 识别 | `/image` | `/cmd_vel` |
| line_follower_perception | ResNet18 语义分割 | `/image` | 线偏差话题 |

> 更具体的部署安装步骤见各子包内 `README_cn.md`（含 tros foxy/humble 版本差异说明）。