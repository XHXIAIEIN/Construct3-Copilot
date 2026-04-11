# Construct 3 实现 Mental Canvas 风格的 3D 图层旋转效果

## 概述

Mental Canvas 的核心视觉效果是将多层 2D 平面画作排列在 3D 空间中，通过摄像机的旋转和平移来揭示图层之间的深度关系。每一层仍然是"扁平的卡片"，但被放置在不同的 Z 深度上。

**Construct 3 完全具备实现这种效果的能力。** 下面是详细的技术分析和实现方案。

---

## C3 关键 3D 特性对照

| Mental Canvas 效果 | C3 对应功能 | API / 属性 |
|---|---|---|
| 图层在不同深度叠放 | 图层 Z 高度 | `ILayer.zElevation` |
| 透视缩放（远小近大） | 透视投影模式 | `ILayout.projection = "perspective"` |
| 摄像机环绕旋转 | 3D 相机旋转 | `Camera3D → RotateCamera` |
| 摄像机平移漫游 | 3D 相机轴向移动 | `Camera3D → MoveAlongCameraAxis` |
| 摄像机自由定位 | 3D 相机注视 | `Camera3D → LookAtPosition` |
| 消失点控制 | 消失点设置 | `ILayout.setVanishingPoint()` |
| 单个元素的 3D 深度 | 对象 Z 高度 | `IWorldInstance.zElevation` |
| 3D 渲染 | 图层渲染模式 | `ILayer.renderingMode = "3d"` |

---

## 实现方案

### 方案一：纯事件表实现（推荐入门）

使用 C3 内置事件系统，无需编写脚本。

#### 项目设置

1. **布局属性**：将 `Projection` 设为 `Perspective`（透视投影）
2. **添加 3D Camera 对象**：在项目中添加 `Camera3D` 插件
3. **创建多个图层**：每个图层代表一个 Mental Canvas 的"画面层"

#### 图层结构示例

```
Layout: "MentalCanvasDemo"
├── Layer "Background"    → Z Elevation: 0     (最远的背景)
├── Layer "MidGround"     → Z Elevation: 200   (中景)
├── Layer "Characters"    → Z Elevation: 400   (角色层)
├── Layer "Foreground"    → Z Elevation: 600   (前景)
└── Layer "UI"            → Z Elevation: 800   (UI 层, 固定)
```

#### 事件表逻辑

```
┌─────────────────────────────────────────────────────────────┐
│ Event Sheet: "3DLayerRotation"                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ── On start of layout ──────────────────────────────────    │
│    Actions:                                                 │
│    ├ Camera3D → Look at position                            │
│    │   Camera X: LayoutWidth/2                              │
│    │   Camera Y: LayoutHeight/2                             │
│    │   Camera Z: 1000                                       │
│    │   Look X: LayoutWidth/2                                │
│    │   Look Y: LayoutHeight/2                               │
│    │   Look Z: 0                                            │
│    │   Up X: 0, Up Y: 1, Up Z: 0                           │
│    └ System → Set CameraAngle to 0                          │
│                                                             │
│ ── Every tick ──────────────────────────────────────────    │
│    Condition: Mouse.IsButtonDown(0)                         │
│    Actions:                                                 │
│    ├ Camera3D → Rotate camera                               │
│    │   Rotate X: Mouse.MovementX * 0.3                      │
│    │   Rotate Y: Mouse.MovementY * 0.3                      │
│    │   Min polar angle: 10                                  │
│    │   Max polar angle: 170                                 │
│    └ (摄像机跟随鼠标拖拽旋转)                                │
│                                                             │
│ ── On mouse wheel ─────────────────────────────────────    │
│    Actions:                                                 │
│    └ Camera3D → Move along camera axis                      │
│      Distance: Mouse.WheelDeltaY * -50                      │
│      Axis: Forward                                          │
│      Which: Camera & look positions                         │
│      (滚轮缩放/推进)                                        │
│                                                             │
│ ── Keyboard: On "R" pressed ───────────────────────────    │
│    Actions:                                                 │
│    └ Camera3D → Look at position                            │
│      (重置到初始视角)                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 方案二：脚本实现（更精细的控制）

使用 Construct 3 的 JavaScript 脚本 API 实现平滑的环绕摄像机。

```javascript
// 在脚本文件中 (e.g., main.js)

// 环绕参数
let orbitAngleX = 0;    // 水平旋转角度
let orbitAngleY = 30;   // 垂直旋转角度 (初始俯视 30°)
let orbitRadius = 1000;  // 环绕半径
let centerX, centerY, centerZ;
let isDragging = false;
let lastMouseX, lastMouseY;

runOnStartup(async runtime => {
    runtime.addEventListener("beforeprojectstart", () => OnBeforeProjectStart(runtime));
});

function OnBeforeProjectStart(runtime) {
    const layout = runtime.layout;
    centerX = layout.width / 2;
    centerY = layout.height / 2;
    centerZ = 300;  // 图层中心深度

    runtime.addEventListener("tick", () => Tick(runtime));

    // 鼠标拖拽控制
    runtime.addEventListener("pointerdown", e => {
        isDragging = true;
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
    });
    runtime.addEventListener("pointerup", () => isDragging = false);
    runtime.addEventListener("pointermove", e => {
        if (!isDragging) return;
        const dx = e.clientX - lastMouseX;
        const dy = e.clientY - lastMouseY;
        orbitAngleX += dx * 0.3;
        orbitAngleY = Math.max(5, Math.min(175, orbitAngleY + dy * 0.3));
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
    });

    // 滚轮缩放
    runtime.addEventListener("wheel", e => {
        orbitRadius = Math.max(200, Math.min(3000, orbitRadius + e.deltaY));
    });

    UpdateCamera(runtime);
}

function Tick(runtime) {
    UpdateCamera(runtime);
}

function UpdateCamera(runtime) {
    // 球面坐标 → 笛卡尔坐标
    const radX = orbitAngleX * Math.PI / 180;
    const radY = orbitAngleY * Math.PI / 180;

    const camX = centerX + orbitRadius * Math.sin(radY) * Math.sin(radX);
    const camY = centerY - orbitRadius * Math.cos(radY);
    const camZ = centerZ + orbitRadius * Math.sin(radY) * Math.cos(radX);

    const camera3d = runtime.objects.Camera3D.getFirstInstance();
    camera3d.lookAtPosition(
        camX, camY, camZ,    // 摄像机位置
        centerX, centerY, centerZ,  // 注视点
        0, 1, 0              // 上方向
    );
}
```

### 方案三：Timeline 动画（预设路径）

适合非交互式的展示动画（类似 Mental Canvas 的自动播放模式）：

1. 创建一个 **Timeline**
2. 在 Timeline 中对 Camera3D 的位置做关键帧动画
3. 设定摄像机沿圆弧或自定义路径移动
4. 播放 Timeline 即可实现自动环绕效果

---

## 图层 Z Elevation 建议值

为了获得最佳的层次感，Z Elevation 的间距应该根据透视效果调整：

| 场景类型 | 图层间距 | 推荐 Z 范围 | 效果 |
|---|---|---|---|
| 绘本/插画风 | 100-200 | 0 ~ 800 | 柔和的层次感 |
| 建筑展示 | 50-100 | 0 ~ 500 | 紧密的结构感 |
| 城市全景 | 200-500 | 0 ~ 2000 | 夸张的纵深感 |
| UI 分层 | 20-50 | 0 ~ 200 | 微妙的深度 |

---

## 与 Mental Canvas 的差异和限制

### C3 可以做到的

- 多图层不同 Z 深度叠放
- 3D 摄像机自由环绕、平移、缩放
- 透视投影带来的远小近大效果
- 鼠标/触摸交互控制摄像机
- 单个精灵独立的 Z 高度
- Timeline 预设摄像机动画路径
- 图层间坐标转换

### C3 做不到或需要额外处理的

| 限制 | 说明 | 变通方案 |
|---|---|---|
| 图层本身不能旋转 | C3 的图层始终面向摄像机（billboard），不能倾斜图层平面 | 使用 3D Shape 或 Mesh deformation 模拟倾斜面 |
| 无矢量笔触 | Mental Canvas 使用矢量线条，C3 是光栅化的 | 使用高分辨率 PNG 或 SVG 转 PNG |
| 无自动深度推断 | Mental Canvas 可以从 2D 画作自动推断深度 | 需要手动为每层设置 Z 值 |
| 图层数量性能 | 过多的 3D 图层会影响渲染性能 | 建议控制在 10-15 层以内 |
| 无曲面图层 | Mental Canvas 的图层可以沿曲面弯曲 | 使用 Mesh deformation API 模拟 |

### 关于"图层旋转"的重要说明

C3 的 3D 图层系统中，**图层本身是不能绕 X/Y 轴旋转的**——图层始终保持平行于 XY 平面。3D 效果完全是通过：

1. 不同图层的 **Z Elevation** 差异
2. **3D Camera** 的位置和旋转
3. **透视投影** 的变形

来实现的。这意味着当摄像机从侧面看时，各图层会呈现为"层叠的薄片"，这与 Mental Canvas 的效果非常相似。

---

## 剪贴板 JSON 示例

以下是创建基础 3D 图层旋转场景所需的事件表 JSON（可直接粘贴到 C3 编辑器）：

```json
{
  "is-c3-clipboard-data": true,
  "type": "events",
  "items": [
    {
      "eventType": "comment",
      "text": "=== 3D Layer Rotation - Mental Canvas Style ==="
    },
    {
      "eventType": "variable",
      "name": "CamAngleX",
      "type": "number",
      "initialValue": "0",
      "comment": "Camera horizontal orbit angle"
    },
    {
      "eventType": "variable",
      "name": "CamAngleY",
      "type": "number",
      "initialValue": "30",
      "comment": "Camera vertical orbit angle"
    },
    {
      "eventType": "variable",
      "name": "OrbitRadius",
      "type": "number",
      "initialValue": "1000",
      "comment": "Distance from camera to center"
    },
    {
      "eventType": "variable",
      "name": "IsDragging",
      "type": "number",
      "initialValue": "0",
      "comment": "Mouse drag state"
    },
    {
      "eventType": "comment",
      "text": "--- Initialize Camera ---"
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-start-of-layout",
          "objectClass": "System",
          "parameters": {}
        }
      ],
      "actions": [
        {
          "id": "look-at-position",
          "objectClass": "Camera3D",
          "parameters": {
            "cam-x": "LayoutWidth/2",
            "cam-y": "LayoutHeight/2",
            "cam-z": "1000",
            "look-x": "LayoutWidth/2",
            "look-y": "LayoutHeight/2",
            "look-z": "300",
            "up-x": "0",
            "up-y": "1",
            "up-z": "0"
          }
        }
      ]
    },
    {
      "eventType": "comment",
      "text": "--- Mouse Drag to Rotate Camera ---"
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-object-clicked",
          "objectClass": "Mouse",
          "parameters": {
            "button": "0"
          }
        }
      ],
      "actions": [
        {
          "id": "set-eventvar-value",
          "objectClass": "System",
          "parameters": {
            "variable": "IsDragging",
            "value": "1"
          }
        }
      ]
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-any-click-release",
          "objectClass": "Mouse",
          "parameters": {
            "button": "0"
          }
        }
      ],
      "actions": [
        {
          "id": "set-eventvar-value",
          "objectClass": "System",
          "parameters": {
            "variable": "IsDragging",
            "value": "0"
          }
        }
      ]
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "every-tick",
          "objectClass": "System",
          "parameters": {}
        },
        {
          "id": "compare-eventvar",
          "objectClass": "System",
          "parameters": {
            "variable": "IsDragging",
            "comparison": "=",
            "value": "1"
          }
        }
      ],
      "actions": [
        {
          "id": "rotate-camera",
          "objectClass": "Camera3D",
          "parameters": {
            "rotate-x": "Mouse.MovementX * 0.3",
            "rotate-y": "Mouse.MovementY * 0.3",
            "min-polar-angle": "10",
            "max-polar-angle": "170"
          }
        }
      ]
    },
    {
      "eventType": "comment",
      "text": "--- Mouse Wheel to Zoom ---"
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-mouse-wheel",
          "objectClass": "Mouse",
          "parameters": {
            "direction": "up"
          }
        }
      ],
      "actions": [
        {
          "id": "move-along-camera-axis",
          "objectClass": "Camera3D",
          "parameters": {
            "distance": "50",
            "axis": "forward",
            "which": "both"
          }
        }
      ]
    },
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-mouse-wheel",
          "objectClass": "Mouse",
          "parameters": {
            "direction": "down"
          }
        }
      ],
      "actions": [
        {
          "id": "move-along-camera-axis",
          "objectClass": "Camera3D",
          "parameters": {
            "distance": "-50",
            "axis": "forward",
            "which": "both"
          }
        }
      ]
    }
  ]
}
```

---

## 推荐的项目配置

在 Construct 3 编辑器中：

1. **项目属性** → `Rendering mode` = `Auto` 或 `WebGPU preferred`
2. **布局属性** → `Projection` = `Perspective`
3. **每个图层** → 设置不同的 `Z elevation` 值
4. **每个图层** → `Rendering mode` = `3D`（如果图层上有 3D 对象）
5. **添加插件** → `Camera3D`、`Mouse`（或 `Touch`）

---

## 参考资料

- [Construct 3 Manual - 3D features](https://www.construct.net/en/make-games/manuals/construct-3/tips-and-guides/3d-in-construct)
- [Construct 3 Manual - 3D Camera](https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/3d-camera)
- [Construct 3 Manual - Layer properties](https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/layers)
