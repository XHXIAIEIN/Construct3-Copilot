# C3事件表开发使用笔记

## 项目概述

- **项目名称**: Construct3AI训练
- **可视区域**: 1920 x 1080
- **场景大小**: 3840 x 2160
- **作者**: ZERO雷刃
- **项目格式版本**: 1
- **保存版本**: 46602

***

## 近期故障复盘（AVG项目）

### A. ⚠️ 打开 ES_UI 报错 `TypeError: expected string`

**现象**:

- 在 Construct 3 编辑器中打开 `ES_UI` 时，前端报错：`main.js:29 Uncaught (in promise) TypeError: expected string`
- 调用栈位于 `eventSheetView / projectResources` 附近
- 该错误发生在**事件表解析阶段**，不是运行时逻辑

**本次项目中的高概率触发点**:

1. `eventType: "variable"` 节点结构过简，缺少常见元字段（如 `comment`、`isStatic`、`isConstant`）
2. `function-block` 的 `functionParameters` 仅有 `name/type/initialValue`，缺少常见 `comment/sid` 字段
3. 事件表字段虽然 JSON 语法正确，但仍可能不满足 C3 当前版本的隐式解析约束

**本次已验证的修复方式（保守修复，不改业务逻辑）**:

1. 给 `ES_UI` 的变量事件补齐字段：
    - `comment: ""`
    - `isStatic: false`
    - `isConstant: false`
2. 给 `ES_UI` / `ES_Audio` 的 `functionParameters` 补齐字段：
    - `comment: ""`
    - `sid: <唯一数字>`
3. 保持原有动作/条件不变，仅做结构兼容修复

**建议排障流程（必须按顺序）**:

1. 先做“最小可开版本”验证：
    - 暂时把 `ES_UI` 降为仅保留 `on-start-of-layout` 空事件
    - 确认事件表可正常打开
2. 使用二分法回填：
    - 每次只回填 1 组 `function-block` 或 1 个 `block`
    - 立刻在编辑器中打开事件表验证
3. 一旦复现，锁定最小坏片段：
    - 优先检查该片段中的参数类型（字符串/布尔/对象选择/枚举）
    - 再检查可选字段是否缺失（特别是变量节点和函数参数节点）
4. 在定位完成前，不叠加新功能逻辑

**额外注意（Windows PowerShell 5.1）**:

- `ConvertFrom-Json` 在部分环境不支持 `-Depth` 参数
- 对大 JSON（如 C3 事件表）做结构校验时，优先使用 Node.js `JSON.parse` 或其他可靠解析工具

***

## ⚠️ 重要易错点

### 1. 创建对象必须使用项目中已添加的对象

**错误**: 在事件表中创建不存在的对象

```
❌ 错误: object-to-create: "新对象"  (项目中未定义)
```

**正确**: 必须先在 `objectTypes/` 中定义对象

```
✅ 正确: object-to-create: "精灵2"  (项目中已定义)
```

> **规则**: `create-object` 动作的 `object-to-create` 参数必须是 `project.c3proj` → `objectTypes.items` 中已存在的对象名称！

***

### 2. 布尔值参数类型区分（重要！）

> **关键规则**: 不同参数的布尔值格式不同！

**使用字符串** **`"true"`/`"false"`** **的参数**:

```json
✅ 正确: 
{
    "id": "create-object",
    "parameters": {
        "create-hierarchy": "false"
    }
}
```

**使用真正布尔值** **`true`/`false`** **的参数**:

```json
✅ 正确: 
{
    "id": "set-layer-interactive",
    "parameters": {
        "interactive": true
    }
}
```

**常见参数类型对照表**:

| 参数名                | 类型  | 示例               |
| ------------------ | --- | ---------------- |
| `create-hierarchy` | 字符串 | `"false"`        |
| `interactive`      | 布尔值 | `true` / `false` |
| `loop`             | 字符串 | `"no"`           |
| `ping-pong`        | 字符串 | `"no"`           |

> **规则**: 需要根据具体参数的要求使用正确的类型！不确定时参考C3剪贴板数据。

***

### 3. 表达式中使用中文对象名

**错误**: 使用英文对象名

```
❌ 错误: Sprite2.数字
❌ 错误: Sprite.变量1
```

**正确**: 使用中文对象名

```
✅ 正确: 精灵2.数字
✅ 正确: 精灵.变量1
```

> **规则**: 在表达式中引用对象时，必须使用对象的中文名称！

***

### 4. 表达式中布尔值用数字表示

**错误**: 在表达式中使用 true/false

```
❌ 错误: 精灵2.是否隐藏 = true
❌ 错误: 精灵2.是否隐藏 ? 9 : 0
```

**正确**: 使用数字 0/1

```
✅ 正确: 精灵2.是否隐藏 = 1
✅ 正确: 精灵2.是否隐藏 = 1 ? 9 : 0
```

***

### 5. ⚠️ 行为插件版本区分（V1 vs V2）- 极其重要！

> **重要**: C3 新版本已禁用 SDK V1 插件，必须使用 V2 版本！

**V1 版本（已禁用，会导致项目无法打开）**:

```json
❌ 错误: "behaviorId": "Solid"        // 大写S
❌ 错误: "behaviorId": "ScrollTo"     // 大写S和T
❌ 错误: "behaviorId": "DestroyOutsideLayout"  // 已废弃
```

**V2 版本（正确）**:

```JSON
✅ 正确: "behaviorId": "solid"        // 全小写
✅ 正确: "behaviorId": "scrollto"     // 全小写
```

**行为插件版本对照表**:

| 行为中文名 | V1版本ID（已废弃）            | V2版本ID（正确）      |
| ----- | ---------------------- | --------------- |
| 实体    | `Solid`                | `solid`         |
| 镜头跟随  | `ScrollTo`             | `scrollto`      |
| 出界销毁  | `DestroyOutsideLayout` | ⚠️ 已移除，用事件替代    |
| 平台    | `Platform`             | `Platform`（未变）  |
| 子弹    | `Bullet`               | `Bullet`（未变）    |
| 计时器   | `Timer`                | `Timer`（未变）     |
| 补间动画  | `Tween`                | `Tween`（未变）     |
| 淡入淡出  | `Fade`                 | `Fade`（未变）      |
| 闪烁    | `Flash`                | `Flash`（未变）     |
| 拖放    | `DragnDrop`            | `DragnDrop`（未变） |
| 视线    | `LOS`                  | `LOS`（未变）       |
| 物理    | `Physics`              | `Physics`（未变）   |

> **规则**:
>
> 1. `solid` 和 `scrollto` 必须使用小写
> 2. `DestroyOutsideLayout` 已废弃，需用事件检测出界后销毁对象
> 3. 其他行为保持大写开头

***

### 6. ⚠️ effectTypes 格式错误（会导致项目无法打开！）

> **重要**: `effectTypes` 必须是**数组**，不能是对象！

**错误格式（会导致 TypeError）**:

```json
❌ 错误: 
"effectTypes": {
    "items": [],
    "subfolders": []
}
```

**正确格式**:

```json
✅ 正确: 
"effectTypes": []
```

> **规则**: 对象类型文件中的 `effectTypes` 字段必须是空数组 `[]` 或包含特效对象的数组！

***

### 7. ⚠️ 对象类型文件格式（严格按照参考项目！）

> **重要**: 对象类型文件格式必须严格遵循参考项目的格式！

**精灵对象 (Sprite) 正确格式**:

```json
{
    "name": "对象名",
    "plugin-id": "Sprite",
    "sid": 123456789,
    "isGlobal": false,
    "editorNewInstanceIsReplica": true,
    "instanceVariables": [
        {
            "name": "变量名",
            "type": "number",
            "desc": "描述",
            "show": true,
            "sid": 123456790
        }
    ],
    "behaviorTypes": [
        {
            "behaviorId": "Timer",
            "name": "计时器",
            "sid": 123456791
        }
    ],
    "effectTypes": [],
    "animations": {
        "items": [
            {
                "frames": [
                    {
                        "width": 100,
                        "height": 100,
                        "originX": 0.5,
                        "originY": 0.5,
                        "originalSource": "",
                        "exportFormat": "lossless",
                        "exportQuality": 0.8,
                        "fileType": "image/png",
                        "imageSpriteId": 123456792,
                        "useCollisionPoly": true,
                        "duration": 1,
                        "tag": ""
                    }
                ],
                "sid": 123456793,
                "name": "默认",
                "isLooping": false,
                "isPingPong": false,
                "repeatCount": 1,
                "repeatTo": 0,
                "speed": 5
            }
        ],
        "subfolders": []
    }
}
```

**文本对象 (Text) 正确格式**:

```json
{
    "name": "文本对象名",
    "plugin-id": "Text",
    "sid": 123456789,
    "isGlobal": false,
    "editorNewInstanceIsReplica": true,
    "instanceVariables": [],
    "behaviorTypes": [],
    "effectTypes": []
}
```

**关键格式规则**:

| 字段                  | 正确格式           | 错误格式                                   |
| ------------------- | -------------- | -------------------------------------- |
| `instanceVariables` | `[]` 数组        | `{ "items": [], "subfolders": [] }` 对象 |
| `behaviorTypes`     | `[]` 数组        | `{ "items": [], "subfolders": [] }` 对象 |
| `effectTypes`       | `[]` 数组        | `{ "items": [], "subfolders": [] }` 对象 |
| 变量描述字段              | `"desc"`       | `"description"`                        |
| 变量显示字段              | `"show": true` | 无此字段                                   |

> **规则**: 必须添加 `isGlobal: false` 和 `editorNewInstanceIsReplica: true` 字段！

***

### 8. ⚠️ 精灵帧格式（严格按照参考项目！）

**帧字段说明**:

| 字段                 | 类型  | 说明                 |
| ------------------ | --- | ------------------ |
| `width`            | 数字  | 帧宽度                |
| `height`           | 数字  | 帧高度                |
| `originX`          | 数字  | 原点X（0\~1）          |
| `originY`          | 数字  | 原点Y（0\~1）          |
| `originalSource`   | 字符串 | 原始源（空字符串）          |
| `exportFormat`     | 字符串 | 导出格式 `"lossless"`  |
| `exportQuality`    | 数字  | 导出质量 `0.8`         |
| `fileType`         | 字符串 | 文件类型 `"image/png"` |
| `imageSpriteId`    | 数字  | 图像精灵ID（唯一）         |
| `useCollisionPoly` | 布尔  | 使用碰撞多边形 `true`     |
| `duration`         | 数字  | 持续时间 `1`           |
| `tag`              | 字符串 | 标签（空字符串）           |

**⚠️ 不要使用的字段**:

- ❌ `collisionPoly` - 不要定义碰撞多边形，使用 `useCollisionPoly: true` 代替
- ❌ `source` - 使用 `originalSource` 代替
- ❌ `properties` - 帧不需要 properties 字段

**动画字段说明**:

| 字段            | 类型  | 说明         |
| ------------- | --- | ---------- |
| `sid`         | 数字  | 唯一ID       |
| `name`        | 字符串 | 动画名称       |
| `isLooping`   | 布尔  | 是否循环       |
| `isPingPong`  | 布尔  | 是否来回播放     |
| `repeatCount` | 数字  | 重复次数 `1`   |
| `repeatTo`    | 数字  | 重复到第几帧 `0` |
| `speed`       | 数字  | 播放速度 `5`   |

> **规则**: 在表达式中，布尔值用 0 (false) 和 1 (true) 表示！

***

### 易错点速查表

| 场景         | 错误                     | 正确                                                     |
| ---------- | ---------------------- | ------------------------------------------------------ |
| 创建对象       | 不存在的对象名                | 项目中已定义的对象                                              |
| 参数布尔值      | 统一使用一种格式               | **根据参数类型区分**                                           |
| 表达式对象名     | `Sprite2` / `Mouse.X`  | `精灵2` / `鼠标.X`                                         |
| 表达式布尔值     | `true` / `false`       | `1` / `0`                                              |
| 创建精灵对象     | 直接创建JSON文件             | 需复制图像并正确命名                                             |
| 补间动画缓动     | `"ease": "linear"`     | `"ease": "default"`                                    |
| 每隔几秒参数     | `"seconds": "1"`       | `"interval-seconds": "1"`                              |
| 无参数动作      | `"parameters": {}`     | 不写parameters字段                                         |
| 无参数条件      | `"parameters": {}`     | 不写parameters字段                                         |
| 出界销毁行为ID   | `"destroyoutside"`     | `"destroy"`                                            |
| 边界约束行为ID   | `"boundtolayout"`      | `"bound"`                                              |
| **隐藏UI图层** | 只设置不可见                 | **必须同时设置不可交互**                                         |
| **变量选择**   | 优先使用全局变量               | **优先使用实例变量**                                           |
| **点击对象检测** | 只用 `on-object-clicked` | **用** **`on-click`** **+** **`cursor-is-over-object`** |
| **创建对象顺序** | 先创建JSON文件              | **先注册到project.c3proj**                                 |
| **透明度范围**  | 使用0\~1                 | **使用0\~100**                                           |
| **触发型条件**  | 放在子事件中                 | **必须作为独立事件**                                           |
| **创建精灵对象** | 只创建JSON文件              | **必须复制图像文件到images文件夹**                                 |

***

### 9. ⚠️ 变量比较条件ID区分（极其重要！）

> **重要**: System对象没有实例变量！比较全局变量/事件变量必须使用`compare-eventvar`！

**比较实例变量（对象实例变量）**:

```json
✅ 正确: 比较对象的实例变量
{
    "id": "compare-instance-variable",
    "objectClass": "精灵",
    "parameters": {
        "instance-variable": "变量1",
        "comparison": 0,
        "value": "1"
    }
}
```

**比较全局变量/事件变量（System对象）**:

```json
✅ 正确: 比较全局变量/事件变量
{
    "id": "compare-eventvar",
    "objectClass": "System",
    "parameters": {
        "variable": "全局变量",
        "comparison": 0,
        "value": "全局变量2"
    }
}
```

**比较布尔值全局变量（为真时）**:

```json
✅ 正确: 布尔值全局变量为真
{
    "id": "compare-boolean-eventvar",
    "objectClass": "System",
    "parameters": {
        "variable": "全局变量3"
    }
}
```

**比较布尔值全局变量（为假时）**:

```json
✅ 正确: 布尔值全局变量为假（使用isInverted取反）
{
    "id": "compare-boolean-eventvar",
    "objectClass": "System",
    "parameters": {
        "variable": "全局变量3"
    },
    "isInverted": true
}
```

**比较两个值**:

```json
✅ 正确: 比较两个值
{
    "id": "compare-two-values",
    "objectClass": "System",
    "parameters": {
        "first-value": "全局变量",
        "comparison": 0,
        "second-value": "全局变量2"
    }
}
```

**常见错误**:

```json
❌ 错误: System对象使用compare-instance-variable
{
    "id": "compare-instance-variable",
    "objectClass": "System",  // System没有实例变量！
    "parameters": {
        "variable": "时段",
        "comparison": 0,
        "value": "5"
    }
}
```

**变量比较条件ID对照表**:

| 条件ID                         | 对象类型           | 用途                |
| ---------------------------- | -------------- | ----------------- |
| `compare-instance-variable`  | 任意对象（非System）  | 比较对象的实例变量         |
| `compare-eventvar`           | System         | 比较全局变量/事件变量       |
| `compare-boolean-eventvar`   | System         | 检查布尔值全局变量是否为真     |
| `compare-two-values`         | System         | 比较两个表达式值          |

> **规则**:
> 1. 比较对象的实例变量使用 `compare-instance-variable`
> 2. 比较全局变量/事件变量使用 `compare-eventvar`
> 3. 检查布尔值全局变量使用 `compare-boolean-eventvar`
> 4. 比较两个表达式值使用 `compare-two-values`

***

### 10. ⚠️ 图层不可见时仍可交互（重要！）

**错误**: 只设置图层不可见

```json
❌ 错误: 只调用 set-layer-visible 设置 invisible
```

**正确**: 同时设置不可见和不可交互

```json
✅ 正确: 
{
    "id": "set-layer-visible",
    "objectClass": "System",
    "parameters": {
        "layer": "UI开关.控制图层",
        "visibility": "invisible"
    }
},
{
    "id": "set-layer-interactive",
    "objectClass": "System",
    "parameters": {
        "layer": "UI开关.控制图层",
        "interactive": false
    }
}
```

> **规则**: C3中图层**不可见或透明时仍然能交互**！必须单独调用 `set-layer-interactive` 设置为不可交互！

**常见场景**:

- UI面板隐藏后，按钮仍可点击
- 透明图层上的对象仍可交互
- 隐藏的菜单仍响应鼠标事件

**图层参数说明**:

| 参数            | 类型      | 说明                          |
| ------------- | ------- | --------------------------- |
| `layer`       | 字符串/表达式 | 可使用实例变量 `UI开关.控制图层`         |
| `visibility`  | 字符串     | `"visible"` 或 `"invisible"` |
| `interactive` | 布尔值     | `true` 或 `false`（不用引号）      |

***

### 11. ⚠️ 优先使用实例变量而非全局变量（重要！）

**错误**: 滥用全局变量

```
❌ 错误: 所有状态都用全局变量存储
```

**正确**: 优先使用实例变量

```json
✅ 正确: 
{
    "name": "UI开关",
    "instanceVariables": [
        {
            "name": "开启状态",
            "type": "number",
            "initialValue": 0
        },
        {
            "name": "控制图层",
            "type": "string",
            "initialValue": "UI"
        }
    ]
}
```

> **规则**: 一般情况下使用**实例变量**而非全局变量！

**实例变量优势**:

| 特性    | 实例变量      | 全局变量    |
| ----- | --------- | ------- |
| 多实例支持 | ✅ 每个实例独立  | ❌ 共享同一值 |
| 面向对象  | ✅ 变量属于对象  | ❌ 全局散乱  |
| 可扩展性  | ✅ 可动态创建多个 | ❌ 固定不变  |

**全局变量适用场景**:

- 游戏总分
- 游戏设置
- 全局状态（暂停、游戏结束）

***

### 12. ⚠️ 点击对象的最佳实践（重要！）

**错误**: 使用 `on-object-clicked`

```json
❌ 错误: 
{
    "id": "on-object-clicked",
    "objectClass": "鼠标",
    "parameters": {
        "mouse-button": "left",
        "click-type": "clicked",
        "object-clicked": "UI开关"
    }
}
```

**正确**: 使用 `on-click` + `cursor-is-over-object` 组合

```json
✅ 正确: 
{
    "id": "on-click",
    "objectClass": "鼠标",
    "parameters": {
        "mouse-button": "left",
        "click-type": "clicked"
    }
},
{
    "id": "cursor-is-over-object",
    "objectClass": "鼠标",
    "parameters": {
        "object": "UI开关"
    }
}
```

> **规则**: 使用 `on-click` + `cursor-is-over-object` 组合，确保用户点错时不松开鼠标移动到对象外能不触发事件！

**两种方式对比**:

| 方式                                   | 问题               |
| ------------------------------------ | ---------------- |
| `on-object-clicked`                  | 按下在对象上，移出后松开仍会触发 |
| `on-click` + `cursor-is-over-object` | 必须按下和松开都在对象上才触发  |

***

### 13. ⚠️ 创建对象的正确顺序（重要！）

**错误**: 先创建JSON文件

```
❌ 错误顺序:
1. 创建 objectTypes/新对象.json
2. 在编辑器中看不到对象
3. 才想起注册到 project.c3proj
```

**正确**: 先注册到project.c3proj

```
✅ 正确顺序:
1. 在 project.c3proj 的 objectTypes.items 中添加对象名
2. 在 project.c3proj 的 usedAddons 中添加插件
3. 创建 objectTypes/新对象.json
```

> **规则**: 必须先在 `project.c3proj` 中注册对象，才能在编辑器中看到！

***

### 14. ⚠️ 补间动画UI效果

> **详细笔记请查看**: [补间动画笔记.md](./补间动画笔记.md)

**常用动画示例**:

```json
✅ 位置动画（滑入效果）:
{
    "id": "tween-two-properties",
    "objectClass": "UI面板",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"滑入\"",
        "property": "position",
        "end-x": "960",
        "end-y": "540",
        "time": "0.5",
        "ease": "easeinoutback",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "no",
        "repeat-count": "1"
    }
}
```

```json
✅ 尺寸动画（点击反馈，ping-pong来回）:
{
    "id": "tween-two-properties",
    "objectClass": "UI开关",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"点击反馈\"",
        "property": "size",
        "end-x": "120",
        "end-y": "120",
        "time": "0.1",
        "ease": "easeinoutquad",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "yes",
        "repeat-count": "1"
    }
}
```

```json
✅ 动画完成事件:
{
    "id": "on-tweens-finished",
    "objectClass": "UI面板",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"滑出\""
    }
}
```

**常用缓动曲线**:

| 缓动曲线            | 效果   | 适用场景    |
| --------------- | ---- | ------- |
| `easeinoutback` | 弹性回弹 | UI弹出、打开 |
| `easeinquad`    | 加速离开 | UI关闭、滑出 |
| `easeinoutsine` | 平滑过渡 | 淡入淡出、悬停 |

***

### 16. ⚠️ 透明度范围是0~~100（不是0~~1）

**错误**: 使用0\~1范围

```json
❌ 错误: 
{
    "id": "tween-one-property",
    "parameters": {
        "property": "offsetOpacity",
        "end-value": "1"  // 错误！应该是100
    }
}
```

**正确**: 使用0\~100范围

```json
✅ 正确: 
{
    "id": "tween-one-property",
    "parameters": {
        "property": "offsetOpacity",
        "end-value": "100"  // 完全不透明
    }
}
```

> **规则**: C3中透明度范围是 **0\~100**，不是0\~1！
>
> - `0` = 完全透明
> - `100` = 完全不透明
> - `offsetOpacity` 使用偏移值，如 `-100` 表示减少100%透明度

***

### 15. ⚠️ 触发型条件不能放在子事件中

**错误**: 在子事件中使用触发型条件

```json
❌ 错误: 
{
    "conditions": [{"id": "on-click", ...}],  // 父事件已有触发条件
    "children": [
        {
            "conditions": [{"id": "on-tweens-finished", ...}],  // 子事件不能再有触发条件！
            "actions": [...]
        }
    ]
}
```

**正确**: 将触发型条件作为独立事件

```json
✅ 正确: 
// 事件1：点击事件
{
    "conditions": [{"id": "on-click", ...}],
    "actions": [...]
}

// 事件2：动画完成事件（独立事件）
{
    "conditions": [{"id": "on-tweens-finished", ...}],
    "actions": [...]
}
```

> **规则**: 触发型条件（如 `on-click`、`on-tweens-finished`、`on-start-of-layout`）**不能放在子事件中**！必须作为独立事件！

**常见触发型条件**:

| 条件ID                 | 说明   |
| -------------------- | ---- |
| `on-click`           | 鼠标点击 |
| `on-start-of-layout` | 场景开始 |
| `on-tweens-finished` | 动画完成 |
| `on-tweens-looped`   | 动画循环 |
| `on-movement`        | 鼠标移动 |

***

### 9. 出界销毁行为ID易错

**错误**: 使用旧版本V1的行为ID

```json
❌ 错误: 
{
    "behaviorId": "destroyoutside",
    "name": "出界销毁"
}
```

**正确**: 使用正确的行为ID

```json
✅ 正确: 
{
    "behaviorId": "destroy",
    "name": "出界销毁",
    "sid": 457814723681448
}
```

> **规则**: 出界销毁行为的 `behaviorId` 是 `"destroy"`，不是 `"destroyoutside"`！`destroyoutside` 是旧版本V1的ID，已废弃！

***

### 8. 无参数动作/条件不要写空parameters

**错误**: 写空的parameters对象

```json
❌ 错误: 
{
    "id": "destroy",
    "objectClass": "精灵",
    "sid": 123,
    "parameters": {}
}

❌ 错误: 
{
    "id": "on-start-of-layout",
    "objectClass": "System",
    "sid": 123,
    "parameters": {}
}
```

**正确**: 不写parameters字段

```json
✅ 正确: 
{
    "id": "destroy",
    "objectClass": "精灵",
    "sid": 123
}

✅ 正确: 
{
    "id": "on-start-of-layout",
    "objectClass": "System",
    "sid": 123
}
```

> **规则**: 当动作或条件没有参数时，不要写空的 `parameters: {}`，直接省略该字段！空的parameters对象会导致 "TypeError: expected finite number" 错误！

***

### 5. 创建精灵对象必须复制图像文件（重要！）

**错误**: 只创建JSON文件，没有图像文件

```
❌ 错误: 只创建 objectTypes/精灵2.json
❌ 错误: 直接引用其他对象的 imageSpriteId
❌ 错误: 图像文件名格式错误
```

**正确**: 复制图像文件并正确命名

```
✅ 正确步骤:
1. 复制图像: images/精灵-animation 1-000.png → images/精灵2-animation 1-000.png
2. 创建对象文件: objectTypes/精灵2.json (使用新的 imageSpriteId)
3. 更新项目注册: project.c3proj → objectTypes.items 添加 "精灵2"
```

**图像命名规则**:

```
{对象名}-{动画名}-{帧序号}.png

示例:
- 精灵2-animation 1-000.png  (精灵2的第1个动画第0帧)
- 精灵3-animation 1-000.png  (精灵3的第1个动画第0帧)
- 精灵-walk-000.png          (精灵的walk动画第0帧)
- 精灵-walk-001.png          (精灵的walk动画第1帧)
```

**⚠️ 多动画对象必须为每个动画创建图像文件**:

```
示例：玩家对象有3个动画（默认、跳跃、死亡）
需要创建3个图像文件：
- 玩家-默认-000.png
- 玩家-跳跃-000.png
- 玩家-死亡-000.png

每个动画的每一帧都需要单独的图像文件！
```

**缺少图像文件时的解决方法**:

1. **检查名称是否正确** - 确保文件名与对象名匹配
2. **复制项目已有的图像** - 从 `images/` 文件夹复制现有图像
3. **重命名使用** - 将复制的图像改为正确的名称

```powershell
# PowerShell 复制图像示例
Copy-Item "images\UI开关-animation 1-000.png" "images\UI选项-animation 1-000.png"
```

**imageSpriteId 规则**:

- 每个精灵对象需要使用唯一的 imageSpriteId
- 不能直接引用其他对象的 imageSpriteId
- 建议使用不重复的大数字作为ID（如 900000001, 900000002...）

> **规则**: 创建精灵对象时，必须同时创建对应的图像文件，并使用唯一的 imageSpriteId！缺少图像文件会导致 "NotFoundError" 错误！

***

### 6. 补间动画缓动曲线参数

**错误**: 使用错误的缓动曲线名称

```
❌ 错误: "ease": "linear"  (某些情况下不识别)
```

**正确**: 使用正确的缓动曲线名称

```
✅ 正确: "ease": "default"        (默认线性)
✅ 正确: "ease": "easeinoutsine"  (正弦缓入缓出)
```

**常用缓动曲线**:

| 值                  | 说明       |
| ------------------ | -------- |
| `default`          | 默认线性（匀速） |
| `easeinoutsine`    | 正弦缓入缓出   |
| `easeinoutquad`    | 二次缓入缓出   |
| `easeinoutcubic`   | 三次缓入缓出   |
| `easeinoutelastic` | 弹性缓入缓出   |

> **规则**: 补间动画的 `ease` 参数建议使用 `default` 作为默认线性！

***

### 7. 每隔几秒条件参数名称

**错误**: 使用错误的参数名称

```
❌ 错误: "seconds": "1"  (参数名错误)
```

**正确**: 使用正确的参数名称

```
✅ 正确: "interval-seconds": "1"
```

> **规则**: `every-x-seconds` 条件的参数名是 `interval-seconds`，不是 `seconds`！

***

### 5.7 子事件结构 (children)

当触发型事件需要搭配其他判断条件时，使用子事件结构：

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-movement",
            "objectClass": "鼠标",
            "sid": 987871094057810
        }
    ],
    "actions": [],
    "sid": 861772814003588,
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "cursor-is-over-object",
                    "objectClass": "鼠标",
                    "sid": 481614144960650,
                    "parameters": {
                        "object": "精灵"
                    }
                }
            ],
            "actions": [],
            "sid": 664603669375151
        }
    ]
}
```

**子事件字段说明**:

| 字段         | 说明                                                     |
| ---------- | ------------------------------------------------------ |
| `children` | 子事件数组，存放在父事件内部                                         |
| 子事件结构      | 与普通事件相同，包含 `eventType`, `conditions`, `actions`, `sid` |

**重要规则**:

1. **每个事件只能有一个触发型条件**（包括子事件）
2. 触发型事件搭配其他判断条件时，使用**子事件**而非同级事件
3. 子事件的优势：**更好的性能**（只在触发时检测二级条件）

**执行流程**:

```
父事件: 鼠标移动 (触发型)
    │
    └── 子事件: 鼠标悬停在精灵上 (每帧检测型)
            │
            └── 动作: (当两个条件都满足时执行)
```

> **性能优化**: 使用子事件结构，二级条件只在触发型条件满足时才检测，而不是每帧都检测！

***

## 一、项目文件结构

```
C3AI训练/
├── project.c3proj              # 主项目配置文件
├── project.uistate.json        # 项目UI状态
├── objecttypes.uistate.json    # 对象类型UI状态
├── eventSheets/                # 事件表目录
│   ├── 事件表 1.json           # 事件表数据
│   └── 事件表 1.uistate.json
├── layouts/                    # 场景目录
│   ├── 场景 1.json             # 场景数据
│   └── 场景 1.uistate.json
├── objectTypes/                # 对象类型定义目录
│   ├── 精灵.json               # 精灵对象类型定义
│   └── 精灵2.json              # 精灵2对象类型定义 (AI添加)
├── images/                     # 图像资源目录
│   ├── 精灵-animation 1-000.png # 精灵动画帧图像
│   └── 精灵2-animation 1-000.png # 精灵2动画帧图像 (AI添加)
├── flowcharts/                 # 流程图目录
│   ├── 流程 1.json
│   └── 流程 1.uistate.json
├── timelines/                  # 时间轴目录
│   ├── 时间轴 1.json
│   └── 时间轴 1.uistate.json
└── icons/                      # 图标资源
    └── icon-*.png
```

***

## 二、核心文件格式

### 2.1 project.c3proj - 主项目文件

```json
{
    "projectFormatVersion": 1,
    "savedWithRelease": 46602,
    "name": "Construct3AI训练",
    "runtime": "c3",
    "useWorker": "auto",
    "bundleAddons": false,
    "usedAddons": [
        {
            "type": "plugin",
            "id": "Sprite",
            "name": "精灵",
            "author": "Scirra",
            "bundled": false
        }
    ],
    "uniqueId": "dh7bsucr0ba",
    "objectTypes": {
        "items": ["精灵", "精灵2"],
        "subfolders": []
    },
    "functionsName": "动作组",
    "containers": [],
    "families": {
        "items": [],
        "subfolders": []
    },
    "layouts": {
        "items": ["场景 1"],
        "subfolders": []
    },
    "eventSheets": {
        "items": ["事件表 1"],
        "subfolders": []
    },
    "timelines": {
        "items": ["时间轴 1"],
        "subfolders": []
    },
    "flowcharts": {
        "items": ["流程 1"],
        "subfolders": []
    },
    "viewportWidth": 1920,
    "viewportHeight": 1080,
    "firstLayout": null
}
```

**关键字段说明**:

| 字段                     | 说明             |
| ---------------------- | -------------- |
| `objectTypes.items`    | 项目中所有对象类型的名称列表 |
| `layouts.items`        | 场景列表           |
| `eventSheets.items`    | 事件表列表          |
| `usedAddons`           | 使用的插件/行为列表     |
| `viewportWidth/Height` | 可视区域尺寸         |

***

### 2.2 layouts/场景 1.json - 场景文件

```json
{
    "name": "场景 1",
    "layers": [
        {
            "name": "图层 0",
            "subLayers": [],
            "instances": [],
            "sid": 708501006904329,
            "effectTypes": [],
            "isInitiallyVisible": true,
            "isInitiallyInteractive": true,
            "isHTMLElementsLayer": false,
            "color": [1, 1, 1, 1],
            "backgroundColor": [0.3686, 0.3686, 0.3686, 1],
            "isTransparent": false,
            "parallaxX": 1,
            "parallaxY": 1,
            "scaleRate": 1,
            "forceOwnTexture": false,
            "renderingMode": "3d",
            "drawOrder": "z-order",
            "useRenderCells": false,
            "blendMode": "normal",
            "zElevation": 0,
            "global": false
        }
    ],
    "sid": 245845989428934,
    "nonworld-instances": [],
    "effectTypes": [],
    "width": 3840,
    "height": 2160,
    "unboundedScrolling": false,
    "vpX": 0.5,
    "vpY": 0.5,
    "projection": "perspective",
    "eventSheet": "事件表 1"
}
```

**关键字段说明**:

| 字段                   | 说明               |
| -------------------- | ---------------- |
| `layers[].instances` | 该图层上的对象实例列表      |
| `width/height`       | 场景尺寸             |
| `eventSheet`         | 绑定的事件表名称         |
| `nonworld-instances` | 非世界对象实例(如数组、字典等) |

***

### 2.3 eventSheets/事件表 1.json - 事件表文件

```json
{
    "name": "事件表 1",
    "events": [],
    "sid": 227077997197082
}
```

**关键字段说明**:

| 字段       | 说明           |
| -------- | ------------ |
| `events` | 事件列表，存放所有事件块 |
| `sid`    | 唯一标识符        |

***

## 三、对象类型格式

### 3.1 对象类型在 project.c3proj 中的注册

```json
"objectTypes": {
    "items": ["精灵", "精灵2", "鼠标"],
    "subfolders": []
}
```

### 3.2 普通对象类型定义文件 (objectTypes/精灵.json)

```json
{
    "name": "精灵",
    "plugin-id": "Sprite",
    "sid": 325112808998092,
    "isGlobal": false,
    "editorNewInstanceIsReplica": true,
    "instanceVariables": [],
    "behaviorTypes": [],
    "effectTypes": [],
    "animations": {
        "items": [
            {
                "frames": [
                    {
                        "width": 250,
                        "height": 250,
                        "originX": 0.5,
                        "originY": 0.5,
                        "originalSource": "",
                        "exportFormat": "lossless",
                        "exportQuality": 0.8,
                        "fileType": "image/png",
                        "imageSpriteId": 2229016,
                        "useCollisionPoly": true,
                        "duration": 1,
                        "tag": ""
                    }
                ],
                "sid": 356103101052990,
                "name": "Animation 1",
                "isLooping": false,
                "isPingPong": false,
                "repeatCount": 1,
                "repeatTo": 0,
                "speed": 10
            }
        ],
        "subfolders": []
    }
}
```

**对象类型文件字段说明**:

| 字段                             | 说明                 |
| ------------------------------ | ------------------ |
| `name`                         | 对象类型名称（中文）         |
| `plugin-id`                    | 插件类型ID (Sprite=精灵) |
| `sid`                          | 对象类型唯一标识符          |
| `isGlobal`                     | 是否为全局对象            |
| `editorNewInstanceIsReplica`   | 新实例是否为副本           |
| `instanceVariables`            | 实例变量列表             |
| `behaviorTypes`                | 行为类型列表             |
| `effectTypes`                  | 效果类型列表             |
| `animations.items`             | 动画列表               |
| `animations.items[].frames`    | 动画帧列表              |
| `animations.items[].name`      | 动画名称               |
| `animations.items[].speed`     | 动画播放速度(FPS)        |
| `animations.items[].isLooping` | 是否循环播放             |

**动画帧字段说明**:

| 字段                 | 说明                  |
| ------------------ | ------------------- |
| `width/height`     | 帧图像尺寸               |
| `originX/originY`  | 原点位置(0-1范围, 0.5=中心) |
| `imageSpriteId`    | 图像资源ID              |
| `duration`         | 帧持续时间               |
| `useCollisionPoly` | 是否使用碰撞多边形           |

### 3.3 全局对象类型定义文件 (objectTypes/鼠标.json)

```json
{
    "name": "鼠标",
    "plugin-id": "Mouse",
    "sid": 624330523597863,
    "singleglobal-inst": {
        "type": "鼠标",
        "properties": {},
        "uid": 4,
        "sid": 694149252350066,
        "tags": ""
    }
}
```

**全局对象特点**:

| 字段                       | 说明           |
| ------------------------ | ------------ |
| `singleglobal-inst`      | 单例全局实例定义     |
| `singleglobal-inst.type` | 对象类型名称       |
| `singleglobal-inst.uid`  | 实例唯一ID       |
| `singleglobal-inst.sid`  | 实例静态ID       |
| 无 `animations`           | 全局对象通常没有动画   |
| 无 `world` 属性             | 全局对象不在场景中有位置 |

**全局对象 vs 普通对象**:

| 特性   | 普通对象 (精灵)      | 全局对象 (鼠标)           |
| ---- | -------------- | ------------------- |
| 实例方式 | `instances` 数组 | `singleglobal-inst` |
| 场景位置 | 有 `world` 属性   | 无位置                 |
| 动画   | 有 `animations` | 通常无                 |
| 实例数量 | 可多个            | 只有一个全局实例            |

> **注意**: 全局对象不需要在场景的 `instances` 中添加实例，它自动存在于所有场景中

***

## 四、对象实例格式

### 4.1 对象实例在场景文件中的定义

```json
{
    "type": "精灵",
    "properties": {
        "initially-visible": true,
        "initial-animation": "Animation 1",
        "initial-frame": 0,
        "enable-collisions": true,
        "live-preview": false
    },
    "uid": 2,
    "sid": 980738103302482,
    "tags": "",
    "instanceVariables": {},
    "behaviors": {},
    "instanceFolderItem": {
        "sid": 980738103302482,
        "expanded": true
    },
    "showing": true,
    "locked": false,
    "world": {
        "x": 607,
        "y": 382,
        "width": 250,
        "height": 250,
        "originX": 0.5,
        "originY": 0.5,
        "color": [1, 1, 1, 1],
        "angle": 0,
        "zElevation": 0
    }
}
```

**对象实例字段说明**:

| 字段                  | 说明             |
| ------------------- | -------------- |
| `type`              | 对象类型名称         |
| `uid`               | 实例唯一ID (运行时使用) |
| `sid`               | 实例静态ID (编辑器使用) |
| `tags`              | 标签             |
| `instanceVariables` | 实例变量值          |
| `behaviors`         | 行为实例数据         |
| `showing`           | 是否在编辑器中显示      |
| `locked`            | 是否锁定           |
| `world`             | 世界坐标属性         |

**world 字段说明**:

| 字段                | 说明                                               |
| ----------------- | ------------------------------------------------ |
| `x/y`             | 场景中的位置坐标                                         |
| `width/height`    | 实例尺寸                                             |
| `originX/originY` | 原点偏移(0-1范围)                                      |
| `color`           | 颜色RGBA (**0-1范围**, 白色=\[1,1,1,1], 红色=\[1,0,0,1]) |
| `angle`           | 旋转角度(弧度)                                         |
| `zElevation`      | Z轴高度                                             |

> **重要**: C3中的颜色值使用 **0-1 范围**，不是 0-255！
>
> - 白色 = `[1, 1, 1, 1]`
> - 红色 = `[1, 0, 0, 1]`
> - 半透明 = `[1, 1, 1, 0.5]`
> - 转换公式: `C3值 = RGB值 / 255`

**properties 字段说明(精灵特有)**:

| 字段                  | 说明       |
| ------------------- | -------- |
| `initially-visible` | 初始是否可见   |
| `initial-animation` | 初始动画名称   |
| `initial-frame`     | 初始帧索引    |
| `enable-collisions` | 是否启用碰撞   |
| `live-preview`      | 是否启用实时预览 |

***

## 五、事件表事件格式

### 5.1 事件基本结构

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "条件ID",
            "objectClass": "对象类",
            "sid": 唯一标识符
        }
    ],
    "actions": [],
    "sid": 事件唯一标识符
}
```

**事件字段说明**:

| 字段           | 说明                   |
| ------------ | -------------------- |
| `eventType`  | 事件类型: "block"(标准事件块) |
| `conditions` | 条件列表                 |
| `actions`    | 动作列表                 |
| `sid`        | 事件唯一标识符              |

**条件字段说明**:

| 字段            | 说明                            |
| ------------- | ----------------------------- |
| `id`          | 条件ID (如 "on-start-of-layout") |
| `objectClass` | 对象类 (如 "System" 表示系统条件)       |
| `sid`         | 条件唯一标识符                       |

### 5.1.1 函数事件结构 (function-block)

```json
{
    "functionName": "动作组1",
    "functionDescription": "",
    "functionCategory": "",
    "functionReturnType": "number",
    "functionCopyPicked": false,
    "functionIsAsync": false,
    "functionParameters": [
        {
            "name": "x",
            "type": "number",
            "initialValue": "0",
            "comment": "",
            "sid": 970747295105665
        }
    ],
    "eventType": "function-block",
    "conditions": [],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [],
            "actions": [
                {
                    "id": "set-function-return-value",
                    "objectClass": "动作组",
                    "parameters": {
                        "value": "x+y"
                    }
                }
            ]
        }
    ]
}
```

**函数事件字段说明**:

| 字段                    | 说明                        |
| --------------------- | ------------------------- |
| `eventType`           | `"function-block"` 表示函数事件 |
| `functionName`        | 函数名称                      |
| `functionDescription` | 函数描述                      |
| `functionCategory`    | 函数分类                      |
| `functionReturnType`  | 返回值类型                     |
| `functionParameters`  | 参数列表                      |
| `functionCopyPicked`  | 是否复制选中对象                  |
| `functionIsAsync`     | 是否异步函数                    |

**返回值类型**:

| 值           | 说明    |
| ----------- | ----- |
| `"none"`    | 无返回值  |
| `"number"`  | 返回数字  |
| `"string"`  | 返回字符串 |
| `"boolean"` | 返回布尔值 |

**函数参数结构**:

| 字段             | 说明                                         |
| -------------- | ------------------------------------------ |
| `name`         | 参数名称                                       |
| `type`         | 参数类型 (`"number"`, `"string"`, `"boolean"`) |
| `initialValue` | 默认值                                        |
| `comment`      | 注释                                         |

**调用函数方式**:

**1. 无返回值的函数 - 动作调用**:

```json
{
    "callFunction": "函数名",
    "sid": 117822332685940
}
```

**2. 有返回值的函数 - 表达式调用**:

```
动作组.函数名(参数1, 参数2)
```

**示例**:

```json
{
    "id": "set-instvar-value",
    "objectClass": "精灵",
    "parameters": {
        "instance-variable": "变量1",
        "value": "动作组.动作组1(10,20)"
    }
}
```

**函数使用场景对比**:

| 类型   | 返回值                           | 使用方式   | 示例                     |
| ---- | ----------------------------- | ------ | ---------------------- |
| 无返回值 | `"none"`                      | 动作中调用  | `callFunction: "动作组2"` |
| 有返回值 | `"number"/"string"/"boolean"` | 表达式中调用 | `动作组.动作组1(10,20)`      |

> **重要**:
>
> - 有返回值的函数在表达式中使用 `动作组.函数名(参数)` 格式
> - 无返回值的函数使用 `callFunction` 动作调用
> - 函数参数在函数内部直接使用参数名访问
> - `objectClass: "动作组"` 是系统内置的函数对象

### 5.2 常用系统条件ID

| 条件ID                 | 说明     | 类型    |
| -------------------- | ------ | ----- |
| `on-start-of-layout` | 场景开始   | 触发型   |
| `on-end-of-layout`   | 场景结束   | 触发型   |
| `on-load`            | 项目加载完成 | 触发型   |
| `every-tick`         | 每一帧    | 每帧检测型 |
| `compare-two-values` | 比较2值   | 每帧检测型 |
| `every-x-seconds`    | 每X秒    | 触发型   |
| `for`                | 循环     | 每帧检测型 |

### 5.2.2 循环条件 (for)

```json
{
    "id": "for",
    "objectClass": "System",
    "sid": 282981885980290,
    "parameters": {
        "name": "\"创建对象\"",
        "start-index": "0",
        "end-index": "9"
    }
}
```

**循环参数说明**:

| 参数            | 类型  | 说明             |
| ------------- | --- | -------------- |
| `name`        | 字符串 | 循环名称（用于获取循环索引） |
| `start-index` | 字符串 | 起始索引           |
| `end-index`   | 字符串 | 结束索引           |

**循环表达式**:

| 表达式                 | 说明              |
| ------------------- | --------------- |
| `loopindex("循环名称")` | 获取当前循环索引        |
| `loopindex("创建对象")` | 获取"创建对象"循环的当前索引 |

**循环范围**: `start-index` 到 `end-index` (包含两端)

- 例如: `start-index: "0"`, `end-index: "9"` → 循环10次 (0,1,2,3,4,5,6,7,8,9)

> **注意**: 循环名称需要用转义引号 `"\"循环名称\""`

### 5.2.0.1 每隔几秒条件 (every-x-seconds)

| 条件ID              | 说明     | 类型  | 参数                 |
| ----------------- | ------ | --- | ------------------ |
| `every-x-seconds` | 每隔X秒触发 | 触发型 | `interval-seconds` |

**每隔几秒条件示例**:

```json
{
    "id": "every-x-seconds",
    "objectClass": "System",
    "parameters": {
        "interval-seconds": "1.0"
    }
}
```

**参数说明**:

| 参数                 | 类型 | 说明        |
| ------------------ | -- | --------- |
| `interval-seconds` | 数字 | 触发间隔时间（秒） |

### 5.2.0.2 重复条件 (repeat)

| 条件ID     | 说明     | 类型  | 参数      |
| -------- | ------ | --- | ------- |
| `repeat` | 重复执行N次 | 触发型 | `count` |

**重复条件示例**:

```json
{
    "id": "repeat",
    "objectClass": "System",
    "parameters": {
        "count": "random(8)"
    }
}
```

**参数说明**:

| 参数      | 类型     | 说明   |
| ------- | ------ | ---- |
| `count` | 数字/表达式 | 重复次数 |

### 5.2.0.3 组合使用：每隔几秒 + 重复

**事件结构**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "every-x-seconds",
            "objectClass": "System",
            "parameters": {
                "interval-seconds": "1.0"
            }
        }
    ],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "repeat",
                    "objectClass": "System",
                    "parameters": {
                        "count": "random(8)"
                    }
                }
            ],
            "actions": [
                {
                    "callFunction": "创建精灵3"
                }
            ]
        }
    ]
}
```

**执行流程**:

```
每隔1.0秒 (触发型)
    │
    └── 子事件: 重复 random(8) 次 (触发型)
            │
            └── 动作: 调用"创建精灵3"
```

**功能说明**:

- 每1秒触发一次
- 每次触发时，随机重复0-7次调用"创建精灵3"
- `random(8)` 返回 0\~7 的随机整数

> **重要**: "每隔几秒"和"重复"都是触发型条件，需要使用子事件结构组合！

### 5.2.1 鼠标对象条件ID

| 条件ID                    | 说明       | 类型    | 参数                           |
| ----------------------- | -------- | ----- | ---------------------------- |
| `on-click`              | 鼠标点击     | 触发型   | `mouse-button`, `click-type` |
| `on-any-click`          | 任意点击     | 触发型   | 无                            |
| `on-button-released`    | 按钮释放     | 触发型   | `mouse-button`               |
| `on-mouse-wheel`        | 鼠标滚轮     | 触发型   | `direction`                  |
| `on-movement`           | 鼠标移动     | 触发型   | 无                            |
| `on-mouse-down`         | 鼠标按下     | 触发型   | `mouse-button`               |
| `on-mouse-up`           | 鼠标释放     | 触发型   | `mouse-button`               |
| `on-mouse-move`         | 鼠标移动     | 触发型   | 无                            |
| `mouse-button-is-down`  | 按住鼠标     | 每帧检测型 | `mouse-button`               |
| `cursor-is-over-object` | 鼠标悬停在对象上 | 每帧检测型 | `object`                     |

### 5.2.2 精灵对象条件ID

| 条件ID                               | 说明      | 类型    | 参数       |
| ---------------------------------- | ------- | ----- | -------- |
| `on-collision-with-another-object` | 与其他对象碰撞 | 每帧检测型 | `object` |

**碰撞条件结构**:

```json
{
    "id": "on-collision-with-another-object",
    "objectClass": "精灵",
    "sid": 407894494515158,
    "parameters": {
        "object": "精灵2"
    }
}
```

**⚠️ 碰撞检测性能优化**:

> **少的对象检测多的对象，节省性能开销！**

| 字段                  | 说明                |
| ------------------- | ----------------- |
| `objectClass`       | 数量**少**的对象（主动检测方） |
| `parameters.object` | 数量**多**的对象（被动方）   |

**示例**:

| 对象  | 数量        | 角色                        |
| --- | --------- | ------------------------- |
| 精灵  | 少（1个）     | `objectClass`（主动检测方）✅     |
| 精灵2 | 多（右键创建很多） | `parameters.object`（被动方）✅ |

### 5.3 条件类型说明

**触发型条件**:

- 只在特定时刻触发一次
- **条件ID以** **`on-`** **开头**
- 如: `on-start-of-layout`, `on-click`, `on-mouse-down`

**每帧检测型条件**:

- 每一帧都会检测条件是否满足
- **条件ID不以** **`on-`** **开头**
- 如: `compare-two-values`, `mouse-button-is-down`
- 条件满足时执行动作

**如何区分触发型和每帧检测型**:

| 类型    | 命名规律                    | 示例                                                 |
| ----- | ----------------------- | -------------------------------------------------- |
| 触发型   | **以** **`on-`** **开头**  | `on-start-of-layout`, `on-click`, `on-mouse-wheel` |
| 每帧检测型 | **不以** **`on-`** **开头** | `compare-two-values`, `mouse-button-is-down`       |

> **重要规律**:
>
> - 条件ID以 `on-` 开头 → 触发型（只触发一次）
> - 条件ID不以 `on-` 开头 → 每帧检测型（每帧检测）
> - 例如: `on-click` 是触发型，`mouse-button-is-down` 是每帧检测型

> **关键规则 - 事件层级结构**:
>
> - **触发型事件应放在事件的最上级**
> - 其他条件（如循环 `for`、判断等）放在子级
> - 因为父事件是触发型，子事件只会在父事件触发时执行
> - 例如: `场景开始`(触发型) → `for循环`(每帧检测型)
>   - 循环只执行一次（因为父事件只触发一次）
>   - `for` 本身是每帧检测型，但作为子事件时，只在父事件触发时执行

### 5.4 带参数的条件结构

```json
{
    "id": "compare-two-values",
    "objectClass": "System",
    "sid": 唯一标识符,
    "parameters": {
        "first-value": "第一个值",
        "comparison": 比较方式,
        "second-value": "第二个值"
    }
}
```

**比较方式 (comparison) 值**:

| 值 | 含义       |
| - | -------- |
| 0 | 等于 (=)   |
| 1 | 不等于 (≠)  |
| 2 | 小于 (<)   |
| 3 | 小于等于 (≤) |
| 4 | 大于 (>)   |
| 5 | 大于等于 (≥) |

### 5.5 动作结构

```json
{
    "id": "动作ID",
    "objectClass": "目标对象",
    "sid": 唯一标识符,
    "parameters": {
        "参数名": "参数值"
    }
}
```

**动作字段说明**:

| 字段            | 说明                      |
| ------------- | ----------------------- |
| `id`          | 动作ID (如 "set-position") |
| `objectClass` | 目标对象名称                  |
| `sid`         | 动作唯一标识符                 |
| `parameters`  | 动作参数对象                  |

### 5.6 常用精灵动作ID

| 动作ID                | 说明      | 参数                           |
| ------------------- | ------- | ---------------------------- |
| `set-position`      | 设置位置    | `x`, `y`                     |
| `set-x`             | 设置X坐标   | `x`                          |
| `set-y`             | 设置Y坐标   | `y`                          |
| `set-angle`         | 设置角度    | `angle`                      |
| `set-visible`       | 设置可见    | `visible`                    |
| `set-opacity`       | 设置透明度   | `opacity`                    |
| `set-scale`         | 设置缩放    | `scaleX`, `scaleY`           |
| `set-instvar-value` | 设置实例变量值 | `instance-variable`, `value` |
| `add-to-instvar`    | 增加实例变量值 | `instance-variable`, `value` |
| `destroy`           | 销毁对象    | 无                            |

**销毁动作示例** (无参数动作，不写parameters字段):

```json
{
    "id": "destroy",
    "objectClass": "精灵2",
    "sid": 228933240809990
}
```

> **注意**: 销毁动作没有参数，不要写空的 `parameters: {}`，直接省略该字段！

### 5.6.0 系统动作ID

| 动作ID                   | 说明       | 参数                                                                         |
| ---------------------- | -------- | -------------------------------------------------------------------------- |
| `create-object`        | 创建对象     | `object-to-create`, `layer`, `x`, `y`, `create-hierarchy`, `template-name` |
| `go-to-layout-by-name` | 按名称跳转场景  | `layout`                                                                   |
| `go-to-layout`         | 按对象跳转场景  | (无参数，选择场景对象)                                                               |
| `restart-layout`       | 重新开始当前场景 | 无                                                                          |
| `previous-layout`      | 跳转到上一个场景 | 无                                                                          |

**创建对象动作详解**:

```json
{
    "id": "create-object",
    "objectClass": "System",
    "sid": 684372469107119,
    "parameters": {
        "object-to-create": "精灵",
        "layer": "0",
        "x": "100",
        "y": "100",
        "create-hierarchy": "false",
        "template-name": "\"\""
    }
}
```

**参数说明**:

| 参数                 | 类型  | 说明                  |
| ------------------ | --- | ------------------- |
| `object-to-create` | 字符串 | 要创建的对象名称（必须在项目中已定义） |
| `layer`            | 字符串 | 图层名称或索引             |
| `x`                | 字符串 | X坐标                 |
| `y`                | 字符串 | Y坐标                 |
| `create-hierarchy` | 布尔  | 是否创建对象层级（父子对象关系）    |
| `template-name`    | 字符串 | 模板名称（空为 `"\"\"`）    |

**对象层级 (create-hierarchy)**:

- `true`: 创建时同时创建子对象，保持父子关系
- `false`: 只创建对象本身

**继承模板 (template-name)**:

- 在场景中设置好对象属性后，可添加模板名称
- 创建时输入模板名称，将使用模板对象的属性
- 空字符串表示不使用模板: `"\"\"`

**场景跳转动作详解**:

```json
{
    "id": "go-to-layout-by-name",
    "objectClass": "System",
    "sid": 799908860467575,
    "parameters": {
        "layout": "\"游戏\""
    }
}
```

**场景跳转参数说明**:

| 参数       | 类型  | 说明                       |
| -------- | --- | ------------------------ |
| `layout` | 字符串 | 目标场景名称，需要转义引号 `"\"游戏\""` |

**场景跳转方式对比**:

| 方式    | 动作ID                   | 说明              |
| ----- | ---------------------- | --------------- |
| 按名称跳转 | `go-to-layout-by-name` | 通过字符串指定场景名，灵活可变 |
| 按对象跳转 | `go-to-layout`         | 直接选择场景对象，固定不变   |

> **重要**: 场景名称在参数中需要用转义引号 `"\"游戏\""`！

### 5.6.1 注释动作

```json
{
    "type": "comment",
    "text": "这是注释内容"
}
```

**注释动作说明**:

| 字段     | 说明              |
| ------ | --------------- |
| `type` | 固定值 `"comment"` |
| `text` | 注释文本内容          |

> 注释动作不会执行，仅用于代码说明

### 5.6.2 实例变量操作动作

**设置实例变量值**:

```json
{
    "id": "set-instvar-value",
    "objectClass": "精灵",
    "sid": 908670858387010,
    "parameters": {
        "instance-variable": "变量1",
        "value": "Self.变量1+1"
    }
}
```

**增加实例变量值**:

```json
{
    "id": "add-to-instvar",
    "objectClass": "精灵",
    "sid": 299162525771795,
    "parameters": {
        "instance-variable": "变量1",
        "value": "1"
    }
}
```

**参数说明**:

| 参数                  | 说明    |
| ------------------- | ----- |
| `instance-variable` | 变量名称  |
| `value`             | 值或表达式 |

**常用表达式**:

| 表达式          | 说明        |
| ------------ | --------- |
| `Self.变量名`   | 当前对象的实例变量 |
| `Self.变量名+1` | 自身变量加1    |
| `Self.x`     | 自身X坐标     |
| `Self.y`     | 自身Y坐标     |

> **推荐**: 使用 `set-instvar-value` 配合 `Self.变量名+1` 更灵活，可以添加 `max()`, `min()` 等安全值表达式

> **注意**: 参数值在JSON中是字符串类型，如 `"500"` 而不是 `500`

***

## 六、图像资源命名规则

### 6.1 精灵动画帧图像命名格式

```
{对象名称}-{动画名称}-{帧索引}.png
```

示例: `精灵-animation 1-000.png`

- 对象名称: 精灵
- 动画名称: animation 1 (默认动画)
- 帧索引: 000 (3位数字，从000开始)

***

## 七、变更记录

> **变更记录已迁移至独立文件**: [变更记录.md](./变更记录.md)

***

## 八、待学习内容

- [x] 添加对象 (已完成)
- [x] 添加条件 (已完成 - 场景开始触发条件)
- [x] 添加动作 (已完成 - 设置位置动作)
- [ ] 对象实例属性修改
- [x] 变量系统 (已完成 - 实例变量)
- [x] 函数定义 (已完成 - 动作组/有返回值/无返回值)
- [x] 行为添加 (已完成 - 补间动画)
- [x] 多动画/多帧设置 (已完成)
- [x] 多场景系统 (已完成 - 场景跳转)

***

## 九、补间动画行为详解

### 9.1 补间动画动作ID

| 动作ID                   | 说明      | 参数                                                                                                               |
| ---------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| `tween-two-properties` | 双属性补间动画 | `tags`, `property`, `end-x`, `end-y`, `time`, `ease`, `destroy-on-complete`, `loop`, `ping-pong`, `repeat-count` |

### 9.2 补间动画参数说明

| 参数                    | 类型     | 说明                                               |
| --------------------- | ------ | ------------------------------------------------ |
| `tags`                | 字符串    | 动画标签，用于标识和控制                                     |
| `property`            | 字符串    | 属性类型：`position`(位置), `size`(尺寸), `opacity`(透明度)等 |
| `end-x`               | 数字/表达式 | 目标X坐标                                            |
| `end-y`               | 数字/表达式 | 目标Y坐标                                            |
| `time`                | 数字     | 动画时长（秒）                                          |
| `ease`                | 字符串    | 缓动曲线类型                                           |
| `destroy-on-complete` | 字符串    | 动画完成后是否销毁：`"yes"` / `"no"`                       |
| `loop`                | 字符串    | 是否循环：`"yes"` / `"no"`                            |
| `ping-pong`           | 字符串    | 是否来回：`"yes"` / `"no"`                            |
| `repeat-count`        | 数字     | 重复次数                                             |

### 9.3 缓动曲线类型 (ease)

| 值                | 说明     | 效果       |
| ---------------- | ------ | -------- |
| `default`        | 默认线性   | 匀速移动     |
| `linear`         | 线性     | 匀速移动     |
| `easeinoutsine`  | 正弦缓入缓出 | 开始和结束时平滑 |
| `easeinsine`     | 正弦缓入   | 开始时平滑    |
| `easeoutsine`    | 正弦缓出   | 结束时平滑    |
| `easeinoutquad`  | 二次缓入缓出 | 更明显的平滑效果 |
| `easeinoutcubic` | 三次缓入缓出 | 非常平滑     |
| `easeinoutexpo`  | 指数缓入缓出 | 开始慢结束快   |

### 9.4 补间动画示例

**移动到随机位置**:

```json
{
    "id": "tween-two-properties",
    "objectClass": "精灵3",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"移动到随机位置\"",
        "property": "position",
        "end-x": "random(1920)",
        "end-y": "random(1080)",
        "time": "1",
        "ease": "default",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "no",
        "repeat-count": "1"
    }
}
```

**移动到固定位置**:

```json
{
    "id": "tween-two-properties",
    "objectClass": "精灵2",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"移动\"",
        "property": "position",
        "end-x": "动作组.计算移动距离(200)",
        "end-y": "精灵2.Y",
        "time": "1",
        "ease": "easeinoutsine",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "no",
        "repeat-count": "1"
    }
}
```

> **注意**: 缓动曲线 `ease` 参数使用 `"default"` 表示默认线性，而不是 `"linear"`！

***

## 十、计时器行为详解

### 10.1 计时器行为概述

计时器行为用于在对象上创建定时触发的事件。常用于游戏中的周期性事件，如敌人生成、状态更新等。

### 10.2 计时器行为定义

在对象类型文件中添加计时器行为：

```json
{
    "name": "事件管理器",
    "plugin-id": "Sprite",
    "sid": 123456789,
    "behaviorTypes": [
        {
            "behaviorId": "Timer",
            "name": "计时器",
            "sid": 543497563159740
        }
    ]
}
```

**行为字段说明**:

| 字段           | 说明                  |
| ------------ | ------------------- |
| `behaviorId` | 行为ID，计时器为 `"Timer"` |
| `name`       | 行为名称（中文）            |
| `sid`        | 行为唯一标识符             |

### 10.3 启动计时器动作

| 动作ID          | 说明    | 参数                        |
| ------------- | ----- | ------------------------- |
| `start-timer` | 启动计时器 | `duration`, `type`, `tag` |

**启动计时器动作示例**:

```json
{
    "id": "start-timer",
    "objectClass": "事件管理器",
    "behaviorType": "计时器",
    "sid": 123456789,
    "parameters": {
        "duration": "1",
        "type": "regular",
        "tag": "\"创建敌人\""
    }
}
```

**参数说明**:

| 参数         | 类型  | 说明                                  |
| ---------- | --- | ----------------------------------- |
| `duration` | 数字  | 计时器时长（秒）                            |
| `type`     | 字符串 | 计时器类型：`"regular"`（重复）或 `"once"`（单次） |
| `tag`      | 字符串 | 计时器标签，用于标识不同的计时器（需要转义引号）            |

**计时器类型**:

| 值         | 说明               |
| --------- | ---------------- |
| `regular` | 重复计时器，每隔指定时间重复触发 |
| `once`    | 单次计时器，只触发一次      |

### 10.4 计时器触发条件

| 条件ID       | 说明    | 参数    |
| ---------- | ----- | ----- |
| `on-timer` | 计时器触发 | `tag` |

**计时器触发条件示例**:

```json
{
    "id": "on-timer",
    "objectClass": "事件管理器",
    "behaviorType": "计时器",
    "sid": 987654321,
    "parameters": {
        "tag": "\"创建敌人\""
    }
}
```

**参数说明**:

| 参数    | 类型  | 说明                |
| ----- | --- | ----------------- |
| `tag` | 字符串 | 要监听的计时器标签（需要转义引号） |

### 10.5 计时器使用示例

**事件结构**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-start-of-layout",
            "objectClass": "System",
            "sid": 111111111
        }
    ],
    "actions": [
        {
            "id": "start-timer",
            "objectClass": "事件管理器",
            "behaviorType": "计时器",
            "sid": 222222222,
            "parameters": {
                "duration": "1",
                "type": "regular",
                "tag": "\"创建敌人\""
            }
        }
    ],
    "sid": 333333333
},
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-timer",
            "objectClass": "事件管理器",
            "behaviorType": "计时器",
            "sid": 444444444,
            "parameters": {
                "tag": "\"创建敌人\""
            }
        }
    ],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "sid": 555555555,
            "parameters": {
                "object-to-create": "敌人",
                "layer": "0",
                "x": "0",
                "y": "random(1080)",
                "create-hierarchy": "false",
                "template-name": "\"\""
            }
        }
    ],
    "sid": 666666666
}
```

### 10.6 ⚠️ 重要：事件管理器必须放置在场景中

> **关键规则**: 拥有计时器行为的对象（如"事件管理器"）**必须在编辑器中的对应场景里放置一个实例**，计时器才能正常工作！

**操作步骤**:

1. 在 `objectTypes/` 中创建带有计时器行为的对象（如"事件管理器"）
2. 在编辑器中打开目标场景
3. 将"事件管理器"对象拖放到场景中（可以放在任意位置，通常设为透明）
4. 在事件表中使用该对象的计时器行为

**常见事件管理器设置**:

- 使用透明精灵图像
- 放置在场景边缘或不可见区域
- 作为全局事件控制器使用

### 10.7 计时器触发遍历模式（性能优化）

> **关键规则**: 不要在最上级事件中使用遍历（`for-each`），这会导致每帧都遍历所有对象，性能极差！应该使用计时器触发时再遍历。

**❌ 错误做法 - 每帧遍历**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "every-tick",
            "objectClass": "System"
        },
        {
            "id": "for-each",
            "objectClass": "System",
            "parameters": {
                "object": "防御塔"
            }
        }
    ],
    "actions": [...]
}
```

> 这种做法每帧都会遍历所有防御塔，性能开销巨大！

***

### 10.8 for-each遍历对象的正确用法

**场景**: 当鼠标从一个对象移动到另一个同类对象时，需要恢复上一个对象的状态

**❌ 错误做法 - 只用 isInverted**:

```json
{
    "conditions": [
        {
            "id": "cursor-is-over-object",
            "objectClass": "鼠标",
            "parameters": {"object": "UI选项"},
            "isInverted": true
        }
    ],
    "actions": [
        {"id": "tween-two-properties", "objectClass": "UI选项", ...}
    ]
}
```

> 问题：当鼠标从UI选项A移动到UI选项B时，A不会恢复，因为条件只检测"不在UI选项上"，但此时鼠标在B上，条件不满足。

**✅ 正确做法 - 使用for-each遍历**:

```json
{
    "conditions": [
        {
            "id": "for-each",
            "objectClass": "System",
            "parameters": {"object": "UI选项"}
        },
        {
            "id": "cursor-is-over-object",
            "objectClass": "鼠标",
            "parameters": {"object": "UI选项"},
            "isInverted": true
        }
    ],
    "actions": [
        {"id": "tween-two-properties", "objectClass": "UI选项", ...}
    ]
}
```

> **规则**: 当需要处理同类对象之间的切换时，必须使用 `for-each` 遍历每个对象单独判断！

**事件执行顺序**:

```
鼠标移动事件
    │
    ├── 遍历所有UI选项 → 如果鼠标不在当前选项上 → 恢复大小
    │
    └── 检测鼠标是否在UI选项上 → 放大当前选项
```

**关键点**:

- `for-each` 会逐个遍历对象实例
- 每个实例单独判断 `cursor-is-over-object`
- 这样可以正确处理对象之间的切换

***

### 10.9 点击切换时先重置再选中

**场景**: 点击同类对象时，需要先重置其他对象的状态，再选中当前对象

**❌ 错误做法 - 直接设置选中状态**:

```json
{
    "conditions": [
        {"id": "on-click", "objectClass": "鼠标"},
        {"id": "cursor-is-over-object", "objectClass": "鼠标", "parameters": {"object": "UI选项"}}
    ],
    "actions": [
        {"id": "set-instvar-value", "objectClass": "UI选项", "parameters": {"instance-variable": "选中状态", "value": "1"}},
        {"id": "tween-two-properties", "objectClass": "UI选项", ...}
    ]
}
```

> 问题：点击UI选项A后，再点击UI选项B，A不会恢复，因为只设置了当前选中，没有重置其他。

**✅ 正确做法 - 父事件重置，子事件选中**:

```json
{
    "conditions": [
        {"id": "on-click", "objectClass": "鼠标"},
        {"id": "cursor-is-over-object", "objectClass": "鼠标", "parameters": {"object": "UI选项"}}
    ],
    "actions": [
        {"id": "set-instvar-value", "objectClass": "UI选项", "parameters": {"instance-variable": "选中状态", "value": "0"}},
        {"id": "tween-two-properties", "objectClass": "UI选项", "parameters": {"property": "scale", "end-x": "1", "end-y": "1", ...}},
        {"id": "tween-one-property", "objectClass": "UI选项", "parameters": {"property": "offsetAngle", "end-value": "0", ...}}
    ],
    "children": [
        {
            "conditions": [
                {"id": "cursor-is-over-object", "objectClass": "鼠标", "parameters": {"object": "UI选项"}}
            ],
            "actions": [
                {"id": "set-instvar-value", "objectClass": "UI选项", "parameters": {"instance-variable": "选中状态", "value": "1"}},
                {"id": "tween-two-properties", "objectClass": "UI选项", ...}
            ]
        }
    ]
}
```

> **规则**: 点击切换时，父事件先重置所有对象，子事件再选中当前对象！

**执行顺序**:

```
点击UI选项事件
    │
    ├── 父事件动作（应用到所有UI选项）
    │   ├── 选中状态 = 0
    │   ├── 缩放 = 1
    │   └── 角度 = 0
    │
    └── 子事件（只应用到当前悬停的UI选项）
        ├── 选中状态 = 1
        └── 播放选中动画
```

**✅ 正确做法 - 计时器触发遍历**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-timer",
            "objectClass": "防御塔",
            "behaviorType": "计时器",
            "parameters": {
                "tag": "\"创建子弹\""
            }
        },
        {
            "id": "for-each",
            "objectClass": "System",
            "parameters": {
                "object": "防御塔"
            }
        }
    ],
    "actions": [...]
}
```

> 计时器每秒触发一次，只在触发时遍历，性能大幅提升！

**性能对比**:

| 方式    | 触发频率     | 性能影响 |
| ----- | -------- | ---- |
| 每帧遍历  | 60次/秒    | 极高 ❌ |
| 计时器遍历 | 1次/秒（可调） | 低 ✅  |

**适用场景**:

| 场景      | 推荐方式              |
| ------- | ----------------- |
| UI每帧刷新  | `every-tick` + 遍历 |
| 定时创建对象  | 计时器 + 遍历          |
| 定时检测/攻击 | 计时器 + 遍历          |

### 10.8 选择最近/最远对象条件

| 条件ID                   | 说明         | 参数                |
| ---------------------- | ---------- | ----------------- |
| `pick-nearestfurthest` | 选择最近或最远的对象 | `which`, `x`, `y` |

**选择最近对象示例**:

```json
{
    "id": "pick-nearestfurthest",
    "objectClass": "敌人",
    "sid": 137758147376439,
    "parameters": {
        "which": "nearest",
        "x": "防御塔.X",
        "y": "防御塔.Y"
    }
}
```

**参数说明**:

| 参数      | 类型     | 说明                                |
| ------- | ------ | --------------------------------- |
| `which` | 字符串    | `"nearest"`（最近）或 `"furthest"`（最远） |
| `x`     | 数字/表达式 | 参考点X坐标                            |
| `y`     | 数字/表达式 | 参考点Y坐标                            |

**使用场景**:

- 防御塔攻击最近的敌人
- AI追踪最近的目标
- 寻找最近的拾取物

***

## 十一、子事件判断模式

### 11.1 敌人死亡判断模式

> **关键规则**: 死亡判断应该放在触发事件的子事件中，先执行扣血，再在子事件中判断是否死亡。

**事件结构**:

```
父事件: 子弹碰撞敌人
    │
    ├── 动作: 敌人扣血
    ├── 动作: 销毁子弹
    │
    └── 子事件: 判断敌人血量 <= 0
            │
            ├── 动作: 销毁敌人
            ├── 动作: 获得金币
            └── 动作: 更新敌人数量
```

**JSON示例**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-collision-with-another-object",
            "objectClass": "子弹",
            "parameters": {
                "object": "敌人"
            }
        }
    ],
    "actions": [
        {
            "id": "add-to-instvar",
            "objectClass": "敌人",
            "parameters": {
                "instance-variable": "血量",
                "value": "-子弹.伤害"
            }
        },
        {
            "id": "destroy",
            "objectClass": "子弹"
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "compare-instance-variable",
                    "objectClass": "敌人",
                    "parameters": {
                        "instance-variable": "血量",
                        "comparison": 2,
                        "value": "0"
                    }
                }
            ],
            "actions": [
                {
                    "id": "destroy",
                    "objectClass": "敌人"
                },
                {
                    "id": "add-to-eventvar",
                    "objectClass": "System",
                    "parameters": {
                        "variable": "金币",
                        "value": "10"
                    }
                }
            ]
        }
    ]
}
```

**为什么使用子事件？**

1. **逻辑清晰**: 先扣血，再判断死亡，符合游戏逻辑
2. **性能优化**: 死亡判断只在碰撞发生时检测，而不是每帧检测
3. **代码组织**: 相关逻辑集中在一起，易于维护

***

## 十二、子弹行为详解

### 12.1 子弹角度设置

> **关键规则**: 修改子弹对象的 `set-angle` 只会改变图像的旋转角度，**不会改变子弹行为的移动方向**！需要使用 `set-angle-of-motion` 来设置移动角度。

**两种角度的区别**:

| 动作ID                  | 说明     | 影响范围       |
| --------------------- | ------ | ---------- |
| `set-angle`           | 设置对象角度 | 只改变图像旋转    |
| `set-angle-of-motion` | 设置移动角度 | 改变子弹行为移动方向 |

### 12.2 正确的子弹创建顺序

> **重要**: 必须先设置速度，再设置移动角度，否则角度设置可能不生效！

**✅ 正确顺序**:

```json
{
    "eventType": "block",
    "conditions": [...],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "parameters": {
                "object-to-create": "子弹",
                "layer": "0",
                "x": "防御塔.X",
                "y": "防御塔.Y",
                "create-hierarchy": true,
                "template-name": "\"\""
            }
        },
        {
            "id": "set-instvar-value",
            "objectClass": "子弹",
            "parameters": {
                "instance-variable": "伤害",
                "value": "防御塔.攻击力"
            }
        },
        {
            "id": "set-angle",
            "objectClass": "子弹",
            "parameters": {
                "angle": "angle(防御塔.X, 防御塔.Y, 敌人.X, 敌人.Y)"
            }
        },
        {
            "id": "set-speed",
            "objectClass": "子弹",
            "behaviorType": "子弹移动",
            "parameters": {
                "speed": "500"
            }
        },
        {
            "id": "set-angle-of-motion",
            "objectClass": "子弹",
            "behaviorType": "子弹移动",
            "parameters": {
                "angle": "angle(防御塔.X, 防御塔.Y, 敌人.X, 敌人.Y)"
            }
        }
    ]
}
```

**动作执行顺序**:

1. 创建子弹对象
2. 设置实例变量（伤害值）
3. 设置图像角度（视觉旋转）
4. 设置子弹速度 ⬅️ **必须先设置速度**
5. 设置移动角度 ⬅️ **再设置移动角度**

### 12.3 子弹行为动作ID

| 动作ID                  | 说明     | 参数        |
| --------------------- | ------ | --------- |
| `set-speed`           | 设置子弹速度 | `speed`   |
| `set-angle-of-motion` | 设置移动角度 | `angle`   |
| `set-gravity`         | 设置重力   | `gravity` |
| `set-bounce`          | 设置反弹   | `bounce`  |

### 12.4 角度计算表达式

**计算两点之间的角度**:

```
angle(起点X, 起点Y, 终点X, 终点Y)
```

**示例**:

```
angle(防御塔.X, 防御塔.Y, 敌人.X, 敌人.Y)
```

> 返回从防御塔指向敌人的角度（弧度）

***

## 十三、出界销毁行为

### 13.1 行为概述

"出界销毁"行为（Destroy Outside Layout）会自动销毁离开场景边界的对象，无需编写任何事件。

### 13.2 行为定义

在对象类型文件中添加出界销毁行为：

```json
{
    "name": "子弹",
    "behaviorTypes": [
        {
            "behaviorId": "Bullet",
            "name": "子弹移动",
            "sid": 800000000000003
        },
        {
            "behaviorId": "destroy",
            "name": "出界销毁",
            "sid": 457814723681448
        }
    ]
}
```

**行为字段说明**:

| 字段           | 说明                                                     |
| ------------ | ------------------------------------------------------ |
| `behaviorId` | 行为ID，固定为 `"destroy"` ⚠️ **不是** **`"destroyoutside"`！** |
| `name`       | 行为名称（中文）                                               |
| `sid`        | 行为唯一标识符                                                |

> **重要**: `behaviorId` 是 `"destroy"`，不是 `"destroyoutside"`！`destroyoutside` 是旧版本V1的ID，已废弃！

### 13.3 使用方式

> **关键规则**: 只需在对象上添加"出界销毁"行为即可，**无需编写任何事件**！行为会自动检测并销毁出界对象。

**适用场景**:

- 子弹飞出屏幕
- 粒子效果
- 临时生成的对象

### 13.4 与手动事件的对比

| 方式       | 代码量  | 性能   | 维护性      |
| -------- | ---- | ---- | -------- |
| 手动判断坐标销毁 | 多个事件 | 每帧检测 | 需要维护边界值  |
| 出界销毁行为   | 无需事件 | 内置优化 | 自动适应场景尺寸 |

**❌ 旧方式 - 手动判断（不推荐）**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "compare-two-values",
            "objectClass": "System",
            "parameters": {
                "first-value": "子弹.X",
                "comparison": 4,
                "second-value": "1920"
            }
        }
    ],
    "actions": [
        {
            "id": "destroy",
            "objectClass": "子弹"
        }
    ]
}
```

**✅ 新方式 - 出界销毁行为（推荐）**:
只需在对象定义中添加行为，无需任何事件！

### 13.5 在project.c3proj中注册

```json
{
    "type": "behavior",
    "id": "destroy",
    "name": "出界销毁",
    "author": "Scirra",
    "bundled": false
}
```

> **注意**: 这里的 `id` 也是 `"destroy"`，不是 `"destroyoutside"`！

***

## 十四、边界约束行为

### 14.1 行为概述

"边界约束"行为（Bound To Layout）会自动将对象限制在场景边界内，无需编写任何事件。

### 14.2 行为定义

在对象类型文件中添加边界约束行为：

```json
{
    "name": "宠物",
    "behaviorTypes": [
        {
            "behaviorId": "bound",
            "name": "边界约束",
            "sid": 768408153061338
        }
    ]
}
```

**行为字段说明**:

| 字段           | 说明                 |
| ------------ | ------------------ |
| `behaviorId` | 行为ID，固定为 `"bound"` |
| `name`       | 行为名称（中文）           |
| `sid`        | 行为唯一标识符            |

### 14.3 约束模式

边界约束行为有2种模式：

| 模式       | 说明                           |
| -------- | ---------------------------- |
| **边界约束** | 整个对象（包括边缘）都限制在场景边界内          |
| **原点约束** | 只限制对象的中心点（原点）在场景边界内，对象边缘可以超出 |

### 14.4 使用方式

> **关键规则**: 只需在对象上添加"边界约束"行为即可，**无需编写任何事件**！行为会自动限制对象位置。

**适用场景**:

- 玩家角色移动限制
- 宠物/宠物活动范围
- 任何需要限制在屏幕内的对象

### 14.5 与手动事件的对比

| 方式       | 代码量  | 性能   | 维护性      |
| -------- | ---- | ---- | -------- |
| 手动判断坐标限制 | 多个事件 | 每帧检测 | 需要维护边界值  |
| 边界约束行为   | 无需事件 | 内置优化 | 自动适应场景尺寸 |

**❌ 旧方式 - 手动判断（不推荐）**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "compare-two-values",
            "objectClass": "System",
            "parameters": {
                "first-value": "宠物.X",
                "comparison": 2,
                "second-value": "50"
            }
        }
    ],
    "actions": [
        {
            "id": "set-x",
            "objectClass": "宠物",
            "parameters": {
                "x": "50"
            }
        }
    ]
}
```

**✅ 新方式 - 边界约束行为（推荐）**:
只需在对象定义中添加行为，无需任何事件！

### 14.6 在project.c3proj中注册

```json
{
    "type": "behavior",
    "id": "bound",
    "name": "边界约束",
    "author": "Scirra",
    "bundled": false
}
```

***

## 十五、SDK版本重要说明

> **关键规则**: 所有行为和插件都只能支持 **SDKV2版本**！必须使用正确的 `behaviorId` 和 `id`！

### 15.1 常用行为ID对照表（SDKV2）

| 行为中文名 | behaviorId | 说明       |
| ----- | ---------- | -------- |
| 计时器   | `Timer`    | 定时触发事件   |
| 出界销毁  | `destroy`  | 自动销毁出界对象 |
| 边界约束  | `bound`    | 限制对象在边界内 |
| 子弹移动  | `Bullet`   | 子弹移动行为   |
| 补间动画  | `Tween`    | 平滑过渡动画   |

### 15.2 易错点

| 错误ID             | 正确ID      | 说明            |
| ---------------- | --------- | ------------- |
| `destroyoutside` | `destroy` | 出界销毁的旧版本ID已废弃 |
| `boundtolayout`  | `bound`   | 边界约束的正确ID     |

***

## 十六、补间动画行为

### 16.1 行为概述

"补间动画"行为（Tween）用于创建平滑的过渡动画，如移动、缩放、旋转、透明度变化等。优先使用补间动画而不是直接设置位置。

### 16.2 行为定义

在对象类型文件中添加补间动画行为：

```json
{
    "name": "宠物",
    "behaviorTypes": [
        {
            "behaviorId": "Tween",
            "name": "补间动画",
            "sid": 100000000000009
        }
    ]
}
```

**行为字段说明**:

| 字段           | 说明                 |
| ------------ | ------------------ |
| `behaviorId` | 行为ID，固定为 `"Tween"` |
| `name`       | 行为名称（中文）           |
| `sid`        | 行为唯一标识符            |

### 16.3 动作ID

| 动作ID                   | 说明      | 参数                                                                                                               |
| ---------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| `tween-two-properties` | 双属性补间动画 | `tags`, `property`, `end-x`, `end-y`, `time`, `ease`, `destroy-on-complete`, `loop`, `ping-pong`, `repeat-count` |

### 16.4 参数说明

| 参数                    | 类型     | 说明                                               |
| --------------------- | ------ | ------------------------------------------------ |
| `tags`                | 字符串    | 动画标签，用于标识和控制（需要转义引号）                             |
| `property`            | 字符串    | 属性类型：`position`(位置), `size`(尺寸), `opacity`(透明度)等 |
| `end-x`               | 数字/表达式 | 目标X坐标                                            |
| `end-y`               | 数字/表达式 | 目标Y坐标                                            |
| `time`                | 数字/表达式 | 动画时长（秒）                                          |
| `ease`                | 字符串    | 缓动曲线类型                                           |
| `destroy-on-complete` | 字符串    | 动画完成后是否销毁：`"yes"` / `"no"`                       |
| `loop`                | 字符串    | 是否循环：`"yes"` / `"no"`                            |
| `ping-pong`           | 字符串    | 是否来回：`"yes"` / `"no"`                            |
| `repeat-count`        | 数字     | 重复次数                                             |

### 16.5 缓动曲线类型 (ease)

| 值                | 说明     | 效果       |
| ---------------- | ------ | -------- |
| `default`        | 默认线性   | 匀速移动     |
| `linear`         | 线性     | 匀速移动     |
| `easeinoutsine`  | 正弦缓入缓出 | 开始和结束时平滑 |
| `easeinsine`     | 正弦缓入   | 开始时平滑    |
| `easeoutsine`    | 正弦缓出   | 结束时平滑    |
| `easeinoutquad`  | 二次缓入缓出 | 更明显的平滑效果 |
| `easeinoutcubic` | 三次缓入缓出 | 非常平滑     |
| `easeinoutexpo`  | 指数缓入缓出 | 开始慢结束快   |

> **注意**: 缓动曲线 `ease` 参数使用 `"default"` 表示默认线性！

### 16.6 位置补间动画示例

**移动到目标位置**:

```json
{
    "id": "tween-two-properties",
    "objectClass": "宠物",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"移动\"",
        "property": "position",
        "end-x": "食物碗.X",
        "end-y": "食物碗.Y",
        "time": "distance(宠物.X, 宠物.Y, 食物碗.X, 食物碗.Y) / 宠物.移动速度",
        "ease": "default",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "no",
        "repeat-count": "1"
    }
}
```

### 16.7 使用场景

| 场景     | 推荐方式                          |
| ------ | ----------------------------- |
| 对象移动   | 补间动画 `tween-two-properties` ✅ |
| 直接设置位置 | `set-position` ❌              |
| 每帧移动   | `move-at-angle` ❌             |

**❌ 旧方式 - 直接设置位置（不推荐）**:

```json
{
    "id": "move-at-angle",
    "objectClass": "宠物",
    "parameters": {
        "angle": "angle(宠物.X, 宠物.Y, 目标.X, 目标.Y)",
        "distance": "宠物.移动速度 * dt"
    }
}
```

**✅ 新方式 - 补间动画移动（推荐）**:

```json
{
    "id": "tween-two-properties",
    "objectClass": "宠物",
    "behaviorType": "补间动画",
    "parameters": {
        "tags": "\"移动\"",
        "property": "position",
        "end-x": "目标.X",
        "end-y": "目标.Y",
        "time": "distance(宠物.X, 宠物.Y, 目标.X, 目标.Y) / 宠物.移动速度",
        "ease": "default",
        "destroy-on-complete": "no",
        "loop": "no",
        "ping-pong": "no",
        "repeat-count": "1"
    }
}
```

### 16.8 在project.c3proj中注册

```json
{
    "type": "behavior",
    "id": "Tween",
    "name": "补间动画",
    "author": "Scirra",
    "bundled": false
}
```

***

## 十七、状态机设计模式

### 17.1 状态机概述

状态机（State Machine）是游戏中常用的设计模式，用于管理对象的不同状态及其转换逻辑。

### 17.2 状态机设计原则

**核心原则**：

1. **状态判断独立**：状态判断应该独立于行为执行，每帧判断
2. **优先级明确**：高优先级状态优先判断，确保状态转换正确
3. **状态互斥**：同一时刻只能处于一个状态
4. **完整覆盖**：所有可能的条件组合都应该有对应的状态

### 17.3 状态机实现方式

**❌ 错误方式 - 在计时器中判断状态**：

```
计时器触发 → 判断条件 → 设置状态 → 执行行为
```

> 问题：状态判断不及时，可能错过状态转换

**✅ 正确方式 - 状态判断与行为执行分离**：

```
每帧：判断条件 → 设置状态（状态机）
计时器：根据当前状态 → 执行行为（AI决策）
```

### 17.4 宠物游戏状态机示例

**状态定义**：

| 状态值 | 状态名 | 行为     |
| --- | --- | ------ |
| 0   | 闲逛  | 随机方向移动 |
| 1   | 饥饿  | 移动到食物碗 |
| 2   | 跟随  | 跟随鼠标位置 |

**状态转换表**：

| 当前状态 | 条件                    | 目标状态  |
| ---- | --------------------- | ----- |
| 任意   | 饥饿值 < 30              | 1（饥饿） |
| 任意   | 饥饿值 >= 30 且 好感度 > 70  | 2（跟随） |
| 任意   | 饥饿值 >= 30 且 好感度 <= 70 | 0（闲逛） |

**优先级顺序**：

```
优先级1（最高）：饥饿值 < 30 → 状态1
优先级2：饥饿值 >= 30 且 好感度 > 70 → 状态2
优先级3：饥饿值 >= 30 且 好感度 <= 70 → 状态0
```

### 17.5 事件表实现

**状态机（每帧判断）**：

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "compare-instance-variable",
            "objectClass": "宠物",
            "parameters": {
                "instance-variable": "饥饿值",
                "comparison": 2,
                "value": "30"
            }
        }
    ],
    "actions": [
        {
            "id": "set-instvar-value",
            "objectClass": "宠物",
            "parameters": {
                "instance-variable": "状态",
                "value": "1"
            }
        }
    ]
}
```

**AI决策（计时器触发）**：

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-timer",
            "objectClass": "宠物",
            "behaviorType": "计时器",
            "parameters": {
                "tag": "\"AI决策\""
            }
        },
        {
            "id": "compare-instance-variable",
            "objectClass": "宠物",
            "parameters": {
                "instance-variable": "状态",
                "comparison": 0,
                "value": "1"
            }
        }
    ],
    "actions": [
        // 执行饥饿状态的行为
    ]
}
```

### 17.6 状态机常见错误

| 错误        | 问题      | 正确做法         |
| --------- | ------- | ------------ |
| 状态判断在计时器中 | 状态转换不及时 | 状态判断每帧执行     |
| 没有优先级     | 状态冲突    | 按优先级顺序判断     |
| 状态转换不完整   | 卡在某个状态  | 确保所有条件都有对应状态 |
| 手动设置状态    | 与状态机冲突  | 让状态机自动管理     |

### 17.7 状态机调试技巧

1. **添加调试显示**：在屏幕上显示当前状态值
2. **检查条件覆盖**：确保所有条件组合都有处理
3. **验证优先级**：高优先级条件应该先判断
4. **测试边界值**：测试状态转换的临界点

***

## 十八、实例变量初始化

### 18.1 初始化的重要性

> **关键规则**：所有实例变量都必须在初始化时设置初始值！未初始化的变量默认为0，可能导致计算错误。

### 18.2 常见错误示例

**错误**：使用未初始化的变量进行计算

```
移动时间 = distance(...) / 宠物.移动速度
```

> 如果 `移动速度` 未初始化（默认为0），会导致除以0错误！

**正确**：在场景开始时初始化所有变量

```json
{
    "id": "set-instvar-value",
    "objectClass": "宠物",
    "parameters": {
        "instance-variable": "移动速度",
        "value": "100"
    }
}
```

### 18.3 初始化检查清单

- [ ] 所有数值型实例变量是否设置了初始值
- [ ] 计算表达式中使用的变量是否已初始化
- [ ] 除法运算的除数是否可能为0
- [ ] 状态变量是否设置了合理的初始状态

***

## 十九、场景图层系统

### 19.1 图层概述

场景（Layout）可以包含多个图层（Layer），图层从上到下堆叠。底层图层通常不透明显示背景，上层图层透明显示内容。

### 19.2 图层结构

```json
{
    "layers": [
        {
            "name": "图层 0",
            "isTransparent": false,
            "backgroundColor": [0.4, 0.6, 0.8, 1]
        },
        {
            "name": "图层 1",
            "isTransparent": true,
            "backgroundColor": [0.37, 0.37, 0.37, 1]
        }
    ]
}
```

### 19.3 图层属性说明

| 属性                       | 类型  | 说明                        |
| ------------------------ | --- | ------------------------- |
| `name`                   | 字符串 | 图层名称                      |
| `isTransparent`          | 布尔  | 是否透明（底层为false，上层为true）    |
| `backgroundColor`        | 数组  | 背景颜色 `[R, G, B, A]`，范围0-1 |
| `isInitiallyVisible`     | 布尔  | 初始是否可见                    |
| `isInitiallyInteractive` | 布尔  | 初始是否可交互                   |
| `parallaxX`              | 数值  | X轴视差系数（1=正常）              |
| `parallaxY`              | 数值  | Y轴视差系数（1=正常）              |
| `scaleRate`              | 数值  | 缩放率（1=正常）                 |
| `zElevation`             | 数值  | Z轴高度                      |
| `instances`              | 数组  | 图层中的对象实例                  |

### 19.4 图层透明度规则

> **关键规则**：最底层图层 `isTransparent: false`（不透明），上层图层 `isTransparent: true`（透明）

**图层堆叠示意**：

```
┌─────────────────────┐
│  图层 1 (透明)       │  ← isTransparent: true
│  显示：UI、特效      │
├─────────────────────┤
│  图层 0 (不透明)     │  ← isTransparent: false
│  显示：背景、地面    │
└─────────────────────┘
```

### 19.5 背景颜色格式

颜色使用RGBA格式，值范围0-1：

```json
"backgroundColor": [R, G, B, A]
```

**示例**：

| 颜色  | RGBA值                |
| --- | -------------------- |
| 白色  | `[1, 1, 1, 1]`       |
| 黑色  | `[0, 0, 0, 1]`       |
| 红色  | `[1, 0, 0, 1]`       |
| 绿色  | `[0, 1, 0, 1]`       |
| 蓝色  | `[0, 0, 1, 1]`       |
| 半透明 | `[1, 1, 1, 0.5]`     |
| 天蓝色 | `[0.4, 0.6, 0.8, 1]` |

### 19.6 添加新图层

在场景JSON的 `layers` 数组中添加新图层对象：

```json
{
    "name": "图层 1",
    "overriden": 0,
    "subLayers": [],
    "instances": [],
    "sid": 725161778165141,
    "effectTypes": [],
    "isInitiallyVisible": true,
    "isInitiallyInteractive": true,
    "isHTMLElementsLayer": false,
    "color": [1, 1, 1, 1],
    "backgroundColor": [0.37, 0.37, 0.37, 1],
    "isTransparent": true,
    "parallaxX": 1,
    "parallaxY": 1,
    "scaleRate": 1,
    "forceOwnTexture": false,
    "renderingMode": "3d",
    "drawOrder": "z-order",
    "useRenderCells": false,
    "blendMode": "normal",
    "zElevation": 0,
    "global": false
}
```

### 19.7 图层使用场景

| 图层位置 | 用途         | isTransparent |
| ---- | ---------- | ------------- |
| 最底层  | 背景、天空、地面   | false         |
| 中间层  | 游戏对象、角色、敌人 | true          |
| 最上层  | UI、分数、按钮   | true          |

### 19.8 图层相关动作

| 动作ID                    | 说明       | 参数                     |
| ----------------------- | -------- | ---------------------- |
| `set-layer-visible`     | 设置图层可见性  | `layer`, `visibility`  |
| `set-layer-interactive` | 设置图层可交互性 | `layer`, `interactive` |

**设置图层可见性示例**：

```json
{
    "id": "set-layer-visible",
    "objectClass": "System",
    "parameters": {
        "layer": "0",
        "visibility": "visible"
    }
}
```

**参数说明**：

| 参数            | 类型  | 说明                                  |
| ------------- | --- | ----------------------------------- |
| `layer`       | 字符串 | 图层名称（需要转义引号，如 `"\"UI\""`）           |
| `visibility`  | 字符串 | `"visible"`（可见）或 `"invisible"`（不可见） |
| `interactive` | 字符串 | `"true"`（可交互）或 `"false"`（不可交互）      |

> **注意**：`layer` 参数必须是图层名称字符串，不能使用实例变量表达式！

### 19.9 图层相关条件

| 条件ID                   | 说明      | 参数      |
| ---------------------- | ------- | ------- |
| `layer-is-visible`     | 图层是否可见  | `layer` |
| `layer-is-interactive` | 图层是否可交互 | `layer` |

**条件示例**：

```json
{
    "id": "layer-is-visible",
    "objectClass": "System",
    "parameters": {
        "layer": "0"
    }
}
```

***

## 二十、条件取反操作

### 20.1 取反概述

> **关键规则**：大部分条件默认判断结果为"真"，使用 `"isInverted": true` 可以对条件结果取反，达到"假"的效果。

### 20.2 取反语法

在条件对象中添加 `"isInverted": true`：

```json
{
    "id": "layer-is-visible",
    "objectClass": "System",
    "parameters": {
        "layer": "0"
    },
    "isInverted": true
}
```

### 20.3 取反效果对比

| 条件                     | isInverted | 实际判断             |
| ---------------------- | ---------- | ---------------- |
| `layer-is-visible`     | 无/`false`  | 图层是否可见（真=可见）     |
| `layer-is-visible`     | `true`     | 图层是否不可见（真=不可见）   |
| `layer-is-interactive` | 无/`false`  | 图层是否可交互（真=可交互）   |
| `layer-is-interactive` | `true`     | 图层是否不可交互（真=不可交互） |

### 20.4 取反使用场景

**场景1：判断图层不可见**

```json
{
    "id": "layer-is-visible",
    "objectClass": "System",
    "parameters": {
        "layer": "UI"
    },
    "isInverted": true
}
```

> 当UI图层不可见时，条件为真

**场景2：判断对象不存在**

```json
{
    "id": "pick-overlapping-point",
    "objectClass": "敌人",
    "parameters": {
        "x": "玩家.X",
        "y": "玩家.Y"
    },
    "isInverted": true
}
```

> 当玩家位置没有敌人时，条件为真

### 20.5 常见需要取反的条件

| 条件类型                     | 默认判断   | 取反后判断   |
| ------------------------ | ------ | ------- |
| `layer-is-visible`       | 图层可见   | 图层不可见   |
| `layer-is-interactive`   | 图层可交互  | 图层不可交互  |
| `is-on-layer`            | 对象在图层上 | 对象不在图层上 |
| `is-visible`             | 对象可见   | 对象不可见   |
| `pick-overlapping-point` | 位置有对象  | 位置无对象   |

### 20.6 注意事项

1. **不是所有条件都需要取反**：有些条件本身就有相反的版本（如 `compare-instance-variable` 可以改变 `comparison` 参数）
2. **取反只影响当前条件**：多个条件之间独立，各自可以单独取反
3. **逻辑清晰**：取反后要确保逻辑含义正确，避免混淆

***

## 二十一、UI开关控制模式

### 21.1 概述

UI开关是游戏中常见的功能，通过一个开关按钮控制UI图层的显示和隐藏。

### 21.2 重要知识点

> **⚠️ 关键规则1**：C3中图层**不可见或透明时仍然能交互**！必须单独设置为不可交互！

> **⚠️ 关键规则2**：一般情况下使用**实例变量**而非全局变量！

### 21.3 UI开关对象设计

```json
{
    "name": "UI开关",
    "instanceVariables": [
        {
            "name": "开启状态",
            "type": "number",
            "initialValue": 0
        },
        {
            "name": "控制图层",
            "type": "string",
            "initialValue": "UI"
        }
    ]
}
```

### 21.4 图层设置

| 图层       | isTransparent | isInitiallyVisible | isInitiallyInteractive |
| -------- | ------------- | ------------------ | ---------------------- |
| 图层 0（背景） | false         | true               | true                   |
| UI（界面）   | true          | false              | false                  |

### 21.5 事件逻辑

**初始化**：

```
场景开始 → 设置UI图层不可见 + 不可交互
```

**点击开关**：

```
点击UI开关 → 切换开启状态(0↔1)
    ├── 状态=1 → 图层可见 + 可交互
    └── 状态=0 → 图层不可见 + 不可交互
```

### 21.6 状态切换技巧

使用 `1 - 当前值` 实现开关切换：

```json
{
    "id": "set-instvar-value",
    "parameters": {
        "instance-variable": "开启状态",
        "value": "1 - UI开关.开启状态"
    }
}
```

> 0 → 1, 1 → 0

### 21.7 完整事件表示例

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-object-clicked",
            "objectClass": "鼠标",
            "parameters": {
                "mouse-button": "left",
                "click-type": "clicked",
                "object-clicked": "UI开关"
            }
        }
    ],
    "actions": [
        {
            "id": "set-instvar-value",
            "objectClass": "UI开关",
            "parameters": {
                "instance-variable": "开启状态",
                "value": "1 - UI开关.开启状态"
            }
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "compare-instance-variable",
                    "objectClass": "UI开关",
                    "parameters": {
                        "instance-variable": "开启状态",
                        "comparison": 0,
                        "value": "1"
                    }
                }
            ],
            "actions": [
                {
                    "id": "set-layer-visible",
                    "objectClass": "System",
                    "parameters": {
                        "layer": "UI开关.控制图层",
                        "visibility": "visible"
                    }
                },
                {
                    "id": "set-layer-interactive",
                    "objectClass": "System",
                    "parameters": {
                        "layer": "UI开关.控制图层",
                        "interactive": true
                    }
                }
            ]
        }
    ]
}
```

***

## 二十二、实例变量 vs 全局变量

### 22.1 选择原则

> **重要**：一般情况下使用**实例变量**而非全局变量！

### 22.2 对比

| 特性    | 实例变量     | 全局变量    |
| ----- | -------- | ------- |
| 作用域   | 对象实例     | 全局      |
| 多实例支持 | ✅ 每个实例独立 | ❌ 共享同一值 |
| 场景切换  | 保留       | 保留      |
| 适用场景  | 对象属性、状态  | 全局设置、分数 |

### 22.3 使用实例变量的优势

1. **多实例独立**：每个对象实例有自己的变量值
2. **面向对象**：变量属于对象，逻辑更清晰
3. **可扩展**：可以动态创建多个相同对象

### 22.4 使用全局变量的场景

- 游戏总分
- 游戏设置
- 全局状态（暂停、游戏结束）

***

## 二十三、事件表层级关系与执行顺序（重要！）

> **来源**: splittsteam项目学习

### 23.1 事件表层级结构概述

事件表采用**树形层级结构**，理解层级关系对于正确编写事件逻辑至关重要。

```
事件表 (events)
├── 事件组 (group)
│   ├── 事件块 (block)
│   │   ├── 条件 (conditions)
│   │   ├── 动作 (actions)
│   │   └── 子事件 (children)
│   │       └── 子事件块 (block)
│   └── 注释 (comment)
├── 函数块 (function-block)
└── 注释 (comment)
```

### 23.2 事件执行顺序规则

> **核心规则**: 事件从上到下依次执行，子事件在父事件条件满足时执行

**执行顺序**:

```
1. 父事件条件判断
   ↓ (条件满足)
2. 执行父事件动作
   ↓
3. 依次执行子事件
   ↓
4. 子事件条件判断
   ↓ (条件满足)
5. 执行子事件动作
```

### 23.3 事件组 (group) 结构

```json
{
    "eventType": "group",
    "disabled": false,
    "title": "宠物AI",
    "description": "",
    "isActiveOnStart": true,
    "children": [
        // 子事件列表
    ],
    "sid": 123456789
}
```

**事件组字段说明**:

| 字段                | 类型  | 说明            |
| ----------------- | --- | ------------- |
| `eventType`       | 字符串 | 固定为 `"group"` |
| `disabled`        | 布尔  | 是否禁用          |
| `title`           | 字符串 | 事件组标题         |
| `description`     | 字符串 | 事件组描述         |
| `isActiveOnStart` | 布尔  | 开始时是否激活       |
| `children`        | 数组  | 子事件列表         |

### 23.4 子事件 (children) 结构

```json
{
    "eventType": "block",
    "conditions": [...],
    "actions": [...],
    "sid": 123456789,
    "children": [
        {
            "eventType": "block",
            "conditions": [...],
            "actions": [...],
            "sid": 987654321
        }
    ]
}
```

**子事件执行规则**:

1. 父事件条件满足后，才检测子事件条件
2. 子事件可以嵌套多层
3. 每层子事件独立判断条件

### 23.5 层级关系实例分析

**实例：宠物状态机**

```
父事件: 计时器触发"状态机"
    │
    ├── 动作: 启动新的计时器
    │
    └── 子事件: 状态判断
            │
            ├── 子事件: 状态="向左移动"
            │       └── 动作: 设置方向、播放动画
            │
            ├── 子事件: 状态="向右移动"
            │       └── 动作: 设置方向、播放动画
            │
            └── 子事件: 状态="待机"
                    └── 动作: 播放待机动画
```

**JSON结构**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-timer",
            "objectClass": "宠物碰撞框",
            "behaviorType": "计时器",
            "parameters": {"tag": "\"状态机\""}
        }
    ],
    "actions": [
        {
            "id": "start-timer",
            "objectClass": "宠物碰撞框",
            "behaviorType": "计时器",
            "parameters": {
                "duration": "random(1,3)",
                "type": "once",
                "tag": "\"状态机\""
            }
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "compare-instance-variable",
                    "objectClass": "宠物碰撞框",
                    "parameters": {
                        "instance-variable": "状态",
                        "comparison": 0,
                        "value": "\"向左移动\""
                    }
                }
            ],
            "actions": [
                {"id": "set-instvar-value", ...},
                {"id": "set-animation", ...}
            ]
        }
    ]
}
```

***

## 二十四、Pick机制详解（核心概念！）

> **来源**: splittsteam项目学习
> **重要性**: ⭐⭐⭐⭐⭐ 不理解Pick机制会导致严重的逻辑错误！

### 24.1 什么是Pick机制？

> **核心概念**: C3中的动作只会作用于\*\*被选中(Picked)\*\*的对象实例，而不是所有同类对象！

**关键规则**:

- 条件会筛选(Pick)符合条件的对象
- 后续动作只作用于被筛选出的对象
- 如果没有正确Pick，动作可能作用于错误的对象或所有对象

### 24.2 常用Pick条件/动作

| 类型 | ID                     | 说明         |
| -- | ---------------------- | ---------- |
| 条件 | `pick-children`        | 选中子对象      |
| 条件 | `pick-parent`          | 选中父对象      |
| 条件 | `pick-nearestfurthest` | 选中最近/最远的对象 |
| 条件 | `for-each`             | 遍历选中每个对象   |
| 条件 | `pick-by-uid`          | 通过UID选中对象  |
| 条件 | `pick-all`             | 选中所有对象     |
| 条件 | `pick-random`          | 随机选中对象     |

### 24.3 pick-children - 选中子对象

> **使用场景**: 父对象被选中后，需要操作其子对象

**语法**:

```json
{
    "id": "pick-children",
    "objectClass": "宠物碰撞框",
    "parameters": {
        "child": "宠物动画家族",
        "which": "own"
    }
}
```

**参数说明**:

| 参数      | 类型  | 说明               |
| ------- | --- | ---------------- |
| `child` | 字符串 | 子对象类型名称          |
| `which` | 字符串 | `"own"` (自己的子对象) |

**完整示例**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "compare-instance-variable",
            "objectClass": "宠物碰撞框",
            "parameters": {
                "instance-variable": "状态",
                "comparison": 0,
                "value": "\"向左移动\""
            }
        }
    ],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "pick-children",
                    "objectClass": "宠物碰撞框",
                    "parameters": {
                        "child": "宠物动画家族",
                        "which": "own"
                    }
                }
            ],
            "actions": [
                {
                    "id": "set-mirrored",
                    "objectClass": "宠物动画家族",
                    "parameters": {"state": "mirrored"}
                },
                {
                    "id": "set-animation",
                    "objectClass": "宠物动画家族",
                    "parameters": {
                        "animation": "\"移动\"",
                        "from": "beginning"
                    }
                }
            ]
        }
    ]
}
```

**执行流程**:

```
1. 条件筛选出状态="向左移动"的宠物碰撞框
2. pick-children 选中该碰撞框的子对象(宠物动画家族)
3. 动作只作用于被选中的子对象
```

### 24.4 pick-parent - 选中父对象

> **使用场景**: 子对象被选中后，需要操作其父对象

**语法**:

```json
{
    "id": "pick-parent",
    "objectClass": "宠物动画家族",
    "parameters": {
        "parent": "宠物碰撞框",
        "which": "own"
    }
}
```

**完整示例**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-animation-finished",
            "objectClass": "宠物动画家族",
            "parameters": {"animation": "\"破壳\""}
        }
    ],
    "actions": [
        {
            "id": "set-animation",
            "objectClass": "宠物动画家族",
            "parameters": {
                "animation": "\"待机\"",
                "from": "beginning"
            }
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "pick-parent",
                    "objectClass": "宠物动画家族",
                    "parameters": {
                        "parent": "宠物碰撞框",
                        "which": "own"
                    }
                }
            ],
            "actions": [
                {
                    "id": "set-enabled",
                    "objectClass": "宠物碰撞框",
                    "behaviorType": "子弹",
                    "parameters": {"state": "enabled"}
                },
                {
                    "id": "start-timer",
                    "objectClass": "宠物碰撞框",
                    "behaviorType": "计时器",
                    "parameters": {
                        "duration": "random(1,3)",
                        "type": "once",
                        "tag": "\"状态机\""
                    }
                }
            ]
        }
    ]
}
```

### 24.5 pick-nearestfurthest - 选中最近/最远的对象

> **使用场景**: 寻找距离某点最近或最远的对象

**语法**:

```json
{
    "id": "pick-nearestfurthest",
    "objectClass": "敌人碰撞框",
    "parameters": {
        "which": "nearest",
        "x": "宠物碰撞框.X",
        "y": "宠物碰撞框.Y"
    }
}
```

**参数说明**:

| 参数      | 类型  | 说明                                 |
| ------- | --- | ---------------------------------- |
| `which` | 字符串 | `"nearest"`(最近) 或 `"furthest"`(最远) |
| `x`     | 数字  | 参考点X坐标                             |
| `y`     | 数字  | 参考点Y坐标                             |

**完整示例 - 敌人寻敌**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "for-each",
            "objectClass": "System",
            "parameters": {"object": "敌人碰撞框"}
        },
        {
            "id": "compare-instance-variable",
            "objectClass": "敌人碰撞框",
            "parameters": {
                "instance-variable": "敌人状态",
                "comparison": 0,
                "value": "\"寻敌\""
            }
        }
    ],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "pick-nearestfurthest",
                    "objectClass": "宠物碰撞框",
                    "parameters": {
                        "which": "nearest",
                        "x": "敌人碰撞框.X",
                        "y": "敌人碰撞框.Y"
                    }
                },
                {
                    "id": "pick-nearestfurthest",
                    "objectClass": "敌人碰撞框",
                    "parameters": {
                        "which": "nearest",
                        "x": "宠物碰撞框.X",
                        "y": "宠物碰撞框.Y"
                    }
                }
            ],
            "actions": [
                // 移动到最近的宠物
            ]
        }
    ]
}
```

### 24.6 for-each - 遍历选中每个对象

> **使用场景**: 需要对每个对象单独处理

**语法**:

```json
{
    "id": "for-each",
    "objectClass": "System",
    "parameters": {"object": "宠物碰撞框"}
}
```

**重要**: `for-each` 会逐个选中对象，后续动作只作用于当前选中的对象！

### 24.7 Pick机制常见错误

| 错误                    | 问题       | 正确做法              |
| --------------------- | -------- | ----------------- |
| 操作子对象前没有pick-children | 操作了所有子对象 | 先pick-children再操作 |
| 操作父对象前没有pick-parent   | 操作了所有父对象 | 先pick-parent再操作   |
| 多个同类对象时直接操作           | 操作了所有对象  | 先用条件筛选再操作         |

***

## 二十五、父子对象层级系统

> **来源**: splittsteam项目学习

### 25.1 父子对象概述

C3支持对象层级关系（Hierarchy），子对象会跟随父对象移动、旋转、缩放。

**层级关系示例**:

```
宠物碰撞框 (父对象)
    ├── 宠物动画 (子对象)
    ├── 宠物点击碰撞框 (子对象)
    ├── 聊天表情 (子对象)
    └── 指示标志 (子对象)
```

### 25.2 创建父子关系 - add-child 动作

**语法**:

```json
{
    "id": "add-child",
    "objectClass": "宠物碰撞框",
    "parameters": {
        "child": "宠物动画",
        "transform-x": true,
        "transform-y": true,
        "transform-w": false,
        "transform-h": false,
        "transform-a": false,
        "transform-o": false,
        "transform-z-elevation": false,
        "transform-visibility": false,
        "destroy-with-parent": true
    }
}
```

**参数说明**:

| 参数                      | 类型  | 说明              |
| ----------------------- | --- | --------------- |
| `child`                 | 字符串 | 子对象名称           |
| `transform-x`           | 布尔  | 是否跟随父对象X坐标      |
| `transform-y`           | 布尔  | 是否跟随父对象Y坐标      |
| `transform-w`           | 布尔  | 是否跟随父对象宽度缩放     |
| `transform-h`           | 布尔  | 是否跟随父对象高度缩放     |
| `transform-a`           | 布尔  | 是否跟随父对象角度旋转     |
| `transform-o`           | 布尔  | 是否跟随父对象透明度      |
| `transform-z-elevation` | 布尔  | 是否跟随父对象Z高度      |
| `transform-visibility`  | 布尔  | 是否跟随父对象可见性      |
| `destroy-with-parent`   | 布尔  | 父对象销毁时是否同时销毁子对象 |

### 25.3 创建子对象的完整流程

**步骤**:

1. 创建子对象实例
2. 设置子对象属性
3. 添加父子关系

**示例**:

```json
{
    "eventType": "block",
    "conditions": [...],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "parameters": {
                "object-to-create": "指示标志",
                "layer": "宠物碰撞框.LayerNumber",
                "x": "宠物碰撞框.X",
                "y": "宠物碰撞框.Y+70",
                "create-hierarchy": false,
                "template-name": "\"\""
            }
        },
        {
            "id": "add-child",
            "objectClass": "宠物碰撞框",
            "parameters": {
                "child": "指示标志",
                "transform-x": true,
                "transform-y": true,
                "transform-w": false,
                "transform-h": false,
                "transform-a": false,
                "transform-o": false,
                "transform-z-elevation": false,
                "transform-visibility": false,
                "destroy-with-parent": true
            }
        }
    ]
}
```

### 25.4 移除父子关系 - remove-from-parent 动作

**语法**:

```json
{
    "id": "remove-from-parent",
    "objectClass": "收获金币"
}
```

**使用场景**: 需要让子对象独立移动时，先移除父子关系

### 25.5 场景文件中的层级数据

在场景文件中，父子关系存储在 `sceneGraphData` 字段：

```json
{
    "type": "拖动框",
    "uid": 6,
    "sceneGraphData": {
        "parent-uid": null,
        "uid": 6,
        "children": [
            {"uid": 8, "flags": {...}},
            {"uid": 9, "flags": {...}}
        ],
        "flags": {
            "x": true,
            "y": true,
            "w": true,
            "h": true,
            "a": true,
            "o": false,
            "v": false,
            "d": true
        }
    }
}
```

**flags 字段说明**:

| 标志  | 说明     |
| --- | ------ |
| `x` | 跟随X坐标  |
| `y` | 跟随Y坐标  |
| `w` | 跟随宽度   |
| `h` | 跟随高度   |
| `a` | 跟随角度   |
| `o` | 跟随透明度  |
| `v` | 跟随可见性  |
| `d` | 随父对象销毁 |

***

## 二十六、家族(Family)系统详解

> **来源**: splittsteam项目学习

### 26.1 家族概述

家族(Family)是C3中用于**对象分组**的功能，允许对一组对象统一添加行为、实例变量和事件。

**splittsteam项目中的家族**:

| 家族名称     | 用途        |
| -------- | --------- |
| 宠物动画家族   | 所有宠物动画对象  |
| 敌人动画家族   | 所有敌人动画对象  |
| 点击碰撞框家族  | 所有可点击的碰撞框 |
| 特效家族     | 所有特效对象    |
| 商店UI\_精灵 | 商店相关的精灵对象 |
| 商店UI\_文本 | 商店相关的文本对象 |

### 26.2 家族在project.c3proj中的定义

```json
"families": {
    "items": [
        "宠物动画家族",
        "敌人动画家族",
        "点击碰撞框家族",
        "特效家族",
        "商店UI_精灵",
        "商店UI_文本"
    ],
    "subfolders": []
}
```

### 26.3 家族的使用场景

**1. 统一行为**:

- 所有宠物动画对象共享相同的动画控制逻辑
- 所有敌人动画对象共享相同的AI行为

**2. 统一实例变量**:

- 家族可以有独立的实例变量
- 所有成员对象自动继承家族的实例变量

**3. 统一事件处理**:

- 可以针对家族编写事件，自动应用于所有成员

### 26.4 家族事件示例

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-animation-finished",
            "objectClass": "宠物动画家族",
            "parameters": {"animation": "\"收获\""}
        }
    ],
    "actions": [
        {
            "id": "set-animation",
            "objectClass": "宠物动画家族",
            "parameters": {
                "animation": "\"待机\"",
                "from": "beginning"
            }
        }
    ]
}
```

> **说明**: 这个事件会应用于"宠物动画家族"中的所有成员对象

### 26.5 家族与Pick机制配合

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "pick-children",
            "objectClass": "宠物碰撞框",
            "parameters": {
                "child": "宠物动画家族",
                "which": "own"
            }
        }
    ],
    "actions": [
        {
            "id": "set-animation",
            "objectClass": "宠物动画家族",
            "parameters": {
                "animation": "\"移动\"",
                "from": "beginning"
            }
        }
    ]
}
```

***

## 二十七、函数系统高级用法

> **来源**: splittsteam项目学习

### 27.1 函数参数传递

**函数定义**:

```json
{
    "functionName": "生成攻击特效1",
    "functionDescription": "",
    "functionCategory": "",
    "functionReturnType": "none",
    "functionCopyPicked": true,
    "functionIsAsync": false,
    "functionParameters": [
        {
            "name": "生成位置X",
            "type": "number",
            "initialValue": "0",
            "comment": ""
        },
        {
            "name": "生成位置Y",
            "type": "number",
            "initialValue": "0",
            "comment": ""
        },
        {
            "name": "生成角度",
            "type": "number",
            "initialValue": "0",
            "comment": ""
        }
    ],
    "eventType": "function-block",
    "conditions": [],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "parameters": {
                "object-to-create": "特效1_2",
                "layer": "LayerIndex(\"战斗特效层\")",
                "x": "生成位置X",
                "y": "生成位置Y",
                "create-hierarchy": true,
                "template-name": "\"\""
            }
        }
    ]
}
```

**调用函数**:

```json
{
    "callFunction": "生成攻击特效1",
    "parameters": [
        "敌人碰撞框.X",
        "敌人碰撞框.Y",
        "angle(敌人碰撞框.X, 敌人碰撞框.Y, 宠物碰撞框.X, 宠物碰撞框.Y)"
    ]
}
```

### 27.2 functionCopyPicked 参数

> **重要**: `functionCopyPicked: true` 表示函数会继承调用者的选中对象状态

**使用场景**:

- 函数内部需要操作调用者选中的对象
- 保持Pick状态的连续性

### 27.3 通过JS调用动作组

**函数定义**:

```json
{
    "functionName": "通过JS调用动作组",
    "functionParameters": [
        {
            "name": "command",
            "type": "string",
            "initialValue": "",
            "comment": ""
        }
    ],
    "eventType": "function-block",
    "conditions": [],
    "actions": [
        {
            "type": "script",
            "language": "javascript",
            "script": [
                "runtime.callFunction(...localVars[\"command\"].split(\",\").map(e => e.trim()))"
            ]
        }
    ]
}
```

**调用方式**:

```json
{
    "callFunction": "通过JS调用动作组",
    "parameters": ["\"动作组名,参数1,参数2\""]
}
```

> **说明**: 这个函数允许通过字符串动态调用其他函数，非常灵活！

***

## 二十八、存档系统详解

> **来源**: splittsteam项目学习

### 28.1 存档系统概述

splittsteam项目使用了完整的存档系统，包括：

- 本地存储 (Local Storage)
- 自动存档
- 存档备份
- 存档检测

### 28.2 存档检测流程

```
游戏启动
    │
    ├── 检测"自动存档"是否存在
    │   ├── 存在 → 读取存档
    │   └── 不存在 → 检测"自动存档备份"
    │       ├── 存在 → 读取备份
    │       └── 不存在 → 读取预设文档
    │
    └── 进入游戏
```

### 28.3 存档相关事件

**检测存档是否存在**:

```json
{
    "id": "check-item-exists",
    "objectClass": "本地存储",
    "parameters": {"key": "\"自动存档\""}
}
```

**存档存在时触发**:

```json
{
    "id": "on-item-exists",
    "objectClass": "本地存储",
    "parameters": {"key": "\"自动存档\""}
}
```

**存档不存在时触发**:

```json
{
    "id": "on-item-missing",
    "objectClass": "本地存储",
    "parameters": {"key": "\"自动存档\""}
}
```

**读取存档**:

```json
{
    "id": "get-item",
    "objectClass": "本地存储",
    "parameters": {"key": "\"自动存档\""}
}
```

**读取完成时触发**:

```json
{
    "id": "on-item-get",
    "objectClass": "本地存储",
    "parameters": {"key": "\"自动存档\""}
}
```

**保存存档**:

```json
{
    "id": "set-item",
    "objectClass": "本地存储",
    "parameters": {
        "key": "\"自动存档\"",
        "value": "SaveStateJSON"
    }
}
```

### 28.4 系统存档动作

**保存游戏状态**:

```json
{
    "id": "save-to-json",
    "objectClass": "System"
}
```

**保存完成时触发**:

```json
{
    "id": "on-save-complete",
    "objectClass": "System"
}
```

**加载游戏状态**:

```json
{
    "id": "load-from-json",
    "objectClass": "System",
    "parameters": {"json": "本地存储.ItemValue"}
}
```

### 28.5 自动存档实现

**自动存档函数**:

```json
{
    "functionName": "自动存档",
    "eventType": "function-block",
    "conditions": [],
    "actions": [
        {
            "id": "save-to-json",
            "objectClass": "System"
        }
    ]
}
```

**保存完成后的处理**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-save-complete",
            "objectClass": "System"
        }
    ],
    "actions": [
        {
            "id": "set-item",
            "objectClass": "本地存储",
            "parameters": {
                "key": "\"自动存档\"",
                "value": "SaveStateJSON"
            }
        }
    ]
}
```

**存档成功后创建备份**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-item-set",
            "objectClass": "本地存储",
            "parameters": {"key": "\"自动存档\""}
        }
    ],
    "actions": [
        {
            "id": "get-item",
            "objectClass": "本地存储",
            "parameters": {"key": "\"自动存档\""}
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "on-item-get",
                    "objectClass": "本地存储",
                    "parameters": {"key": "\"自动存档\""}
                }
            ],
            "actions": [
                {
                    "id": "set-item",
                    "objectClass": "本地存储",
                    "parameters": {
                        "key": "\"自动存档备份\"",
                        "value": "SaveStateJSON"
                    }
                }
            ]
        }
    ]
}
```

***

## 二十九、动画帧标签系统

> **来源**: splittsteam项目学习

### 29.1 动画帧标签概述

C3支持为动画帧添加标签(Tag)，用于在特定帧触发事件。

### 29.2 帧标签定义

在对象类型文件的动画帧中：

```json
{
    "width": 50,
    "height": 100,
    "duration": 1,
    "tag": "\"收获金币\""
}
```

### 29.3 帧标签事件

**动画帧变化时检测**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-animation-frame-changed",
            "objectClass": "宠物动画家族"
        },
        {
            "id": "is-animation-playing",
            "objectClass": "宠物动画家族",
            "parameters": {"animation": "\"收获\""}
        }
    ],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "compare-animation-frame-tag",
                    "objectClass": "宠物动画家族",
                    "parameters": {
                        "comparison": 0,
                        "tag": "\"收获金币\""
                    }
                },
                {
                    "id": "pick-parent",
                    "objectClass": "宠物动画家族",
                    "parameters": {
                        "parent": "宠物碰撞框",
                        "which": "own"
                    }
                },
                {
                    "id": "trigger-once-while-true",
                    "objectClass": "System"
                }
            ],
            "actions": [
                {
                    "callFunction": "收获金币",
                    "parameters": ["宠物碰撞框.宠物id"]
                }
            ]
        }
    ]
}
```

### 29.4 图像点(Image Point)系统

**定义图像点**:

```json
{
    "imagePoints": [
        {
            "name": "表情生成点",
            "x": 0.5,
            "y": 0
        }
    ]
}
```

**使用图像点**:

```json
{
    "id": "create-object",
    "objectClass": "System",
    "parameters": {
        "object-to-create": "聊天表情",
        "layer": "LayerIndex(\"宠物对话层\")",
        "x": "宠物碰撞框.ImagePointX(1)",
        "y": "宠物碰撞框.ImagePointY(1)"
    }
}
```

> **说明**: `ImagePointX(1)` 获取第1个图像点的X坐标（索引从1开始）

***

## 三十、特效系统详解

> **来源**: splittsteam项目学习

### 30.1 特效创建流程

**特效函数示例**:

```json
{
    "functionName": "生成攻击特效1",
    "functionParameters": [
        {"name": "生成位置X", "type": "number"},
        {"name": "生成位置Y", "type": "number"},
        {"name": "生成角度", "type": "number"}
    ],
    "eventType": "function-block",
    "conditions": [],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "parameters": {
                "object-to-create": "特效1_2",
                "layer": "LayerIndex(\"战斗特效层\")",
                "x": "生成位置X",
                "y": "生成位置Y",
                "create-hierarchy": true
            }
        },
        {
            "id": "set-angle",
            "objectClass": "特效1_2",
            "parameters": {"angle": "生成角度"}
        },
        {
            "id": "tween-two-properties",
            "objectClass": "特效1_2",
            "behaviorType": "补间动画",
            "parameters": {
                "tags": "\"攻击效果缩小\"",
                "property": "scale",
                "end-x": "0.02",
                "end-y": "0.02",
                "time": "0.2*timescale",
                "ease": "default",
                "destroy-on-complete": "yes"
            }
        }
    ]
}
```

### 30.2 粒子特效

**创建多个粒子**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "repeat",
            "objectClass": "System",
            "parameters": {"count": "int(random(5,10))"}
        }
    ],
    "actions": [
        {
            "id": "create-object",
            "objectClass": "System",
            "parameters": {
                "object-to-create": "特效1_3",
                "layer": "LayerIndex(\"战斗特效层\")",
                "x": "生成位置X",
                "y": "生成位置Y"
            }
        },
        {
            "id": "set-angle",
            "objectClass": "特效1_3",
            "parameters": {"angle": "random(360)"}
        },
        {
            "id": "tween-two-properties",
            "objectClass": "特效1_3",
            "behaviorType": "补间动画",
            "parameters": {
                "tags": "\"发射粒子\"",
                "property": "position",
                "end-x": "Self.X+cos(random(360))*random(100,200)",
                "end-y": "Self.Y+sin(random(360))*random(100,200)",
                "time": "0.4*timescale",
                "ease": "easeoutquart",
                "destroy-on-complete": "yes"
            }
        }
    ]
}
```

### 30.3 特效销毁

**补间动画完成后销毁**:

```json
{
    "id": "tween-two-properties",
    "parameters": {
        "destroy-on-complete": "yes"
    }
}
```

> **说明**: 设置 `destroy-on-complete: "yes"` 可以在动画完成后自动销毁对象

***

## 三十一、平台行为详解

> **来源**: splittsteam项目学习

### 31.1 平台行为概述

平台行为(Platform)用于创建平台游戏中的角色控制，支持：

- 左右移动
- 跳跃
- 重力
- 站立检测

### 31.2 平台行为定义

```json
{
    "behaviorTypes": [
        {
            "behaviorId": "Platform",
            "name": "平台",
            "sid": 807680340750758
        }
    ]
}
```

### 31.3 平台行为条件

| 条件ID          | 说明     |
| ------------- | ------ |
| `is-on-floor` | 是否在地面上 |
| `is-jumping`  | 是否正在跳跃 |
| `is-falling`  | 是否正在下落 |
| `is-moving`   | 是否正在移动 |
| `on-jump`     | 跳跃时触发  |
| `on-land`     | 落地时触发  |

### 31.4 平台行为动作

| 动作ID               | 说明     | 参数          |
| ------------------ | ------ | ----------- |
| `simulate-control` | 模拟控制   | `control`   |
| `set-enabled`      | 启用/禁用  | `state`     |
| `set-max-speed`    | 设置最大速度 | `max-speed` |
| `set-gravity`      | 设置重力   | `gravity`   |

**模拟控制参数**:

| 值       | 说明   |
| ------- | ---- |
| `left`  | 向左移动 |
| `right` | 向右移动 |
| `jump`  | 跳跃   |

### 31.5 平台行为示例

**随机跳跃**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-timer",
            "objectClass": "宠物碰撞框",
            "behaviorType": "计时器",
            "parameters": {"tag": "\"跳跃状态机\""}
        }
    ],
    "actions": [
        {
            "id": "start-timer",
            "objectClass": "宠物碰撞框",
            "behaviorType": "计时器",
            "parameters": {
                "duration": "random(1,3)",
                "type": "once",
                "tag": "\"跳跃状态机\""
            }
        }
    ],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "is-moving",
                    "objectClass": "宠物碰撞框",
                    "behaviorType": "平台"
                },
                {
                    "id": "is-on-floor",
                    "objectClass": "宠物碰撞框",
                    "behaviorType": "平台"
                }
            ],
            "actions": [],
            "children": [
                {
                    "eventType": "block",
                    "conditions": [
                        {
                            "id": "compare-two-values",
                            "objectClass": "System",
                            "parameters": {
                                "first-value": "random(0,50)",
                                "comparison": 3,
                                "second-value": "宠物碰撞框.跳跃概率"
                            }
                        }
                    ],
                    "actions": [
                        {
                            "id": "simulate-control",
                            "objectClass": "宠物碰撞框",
                            "behaviorType": "平台",
                            "parameters": {"control": "jump"}
                        }
                    ]
                }
            ]
        }
    ]
}
```

**跳跃动画**:

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-jump",
            "objectClass": "宠物碰撞框",
            "behaviorType": "平台"
        }
    ],
    "actions": [],
    "children": [
        {
            "eventType": "block",
            "conditions": [
                {
                    "id": "pick-children",
                    "objectClass": "宠物碰撞框",
                    "parameters": {
                        "child": "宠物动画家族",
                        "which": "own"
                    }
                }
            ],
            "actions": [
                {
                    "id": "set-animation",
                    "objectClass": "宠物动画家族",
                    "parameters": {
                        "animation": "\"准备跳跃\"",
                        "from": "beginning"
                    }
                }
            ]
        }
    ]
}
```

***

## 三十二、视线行为(LOS)

> **来源**: splittsteam项目学习

### 32.1 视线行为概述

视线行为(Line Of Sight)用于检测对象是否能看到目标对象，常用于AI系统。

### 32.2 视线行为定义

```json
{
    "behaviorTypes": [
        {
            "behaviorId": "LOS",
            "name": "视线",
            "sid": 528149911818349
        }
    ]
}
```

### 32.3 视线行为条件

| 条件ID                   | 说明        |
| ---------------------- | --------- |
| `has-line-of-sight-to` | 是否能看到目标对象 |

### 32.4 视线行为动作

| 动作ID               | 说明     |
| ------------------ | ------ |
| `set-range`        | 设置视线范围 |
| `set-cone-of-view` | 设置视野角度 |

***

## 三十三、闪烁行为

> **来源**: splittsteam项目学习

### 33.1 闪烁行为动作

| 动作ID    | 说明 | 参数                                |
| ------- | -- | --------------------------------- |
| `flash` | 闪烁 | `on-time`, `off-time`, `duration` |

**闪烁示例**:

```json
{
    "id": "flash",
    "objectClass": "宠物动画家族",
    "behaviorType": "闪烁",
    "parameters": {
        "on-time": "0.1",
        "off-time": "0.1",
        "duration": "0.5"
    }
}
```

***

## 三十四、镜头跟随行为

> **来源**: splittsteam项目学习

### 34.1 镜头跟随概述

镜头跟随行为用于让镜头自动跟随对象移动。

### 34.2 镜头控制

**设置镜头缩放**:

```json
{
    "id": "set-instvar-value",
    "objectClass": "场景管理器",
    "parameters": {
        "instance-variable": "镜头缩放",
        "value": "100"
    }
}
```

**使用镜头缩放**:

```json
{
    "id": "set-scale",
    "objectClass": "收获金币",
    "parameters": {
        "scale": "100/场景管理器.镜头缩放"
    }
}
```

***

## 三十五、else条件使用

> **来源**: splittsteam项目学习

### 35.1 else条件语法

```json
{
    "id": "else",
    "objectClass": "System"
}
```

### 35.2 else使用示例

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "is-boolean-instance-variable-set",
            "objectClass": "商店按钮",
            "parameters": {"instance-variable": "开关"}
        }
    ],
    "actions": [
        // 开关为true时的动作
    ]
},
{
    "eventType": "block",
    "conditions": [
        {
            "id": "else",
            "objectClass": "System"
        },
        {
            "id": "is-boolean-instance-variable-set",
            "objectClass": "商店按钮",
            "parameters": {"instance-variable": "开关"},
            "isInverted": true
        }
    ],
    "actions": [
        // 开关为false时的动作
    ]
}
```

***

## 三十六、Or条件块

> **来源**: splittsteam项目学习

### 36.1 Or条件块语法

当多个条件只需要满足一个时，使用 `"isOrBlock": true`：

```json
{
    "eventType": "block",
    "conditions": [
        {
            "id": "on-click",
            "objectClass": "Mouse",
            "parameters": {
                "mouse-button": "left",
                "click-type": "clicked"
            }
        },
        {
            "id": "on-window-blur",
            "objectClass": "Browser"
        }
    ],
    "actions": [...],
    "isOrBlock": true
}
```

> **说明**: 上述事件在"鼠标点击"或"窗口失去焦点"时都会触发

***

## 三十七、禁用事件

> **来源**: splittsteam项目学习

### 37.1 禁用事件语法

在事件块中添加 `"disabled": true`：

```json
{
    "eventType": "block",
    "conditions": [...],
    "actions": [...],
    "disabled": true
}
```

### 37.2 禁用单个动作

在动作中添加 `"disabled": true`：

```json
{
    "id": "set-size",
    "objectClass": "收获金币",
    "disabled": true,
    "parameters": {
        "width": "80",
        "height": "60"
    }
}
```

***

## 三十八、常用表达式汇总

> **来源**: splittsteam项目学习

### 38.1 数学表达式

| 表达式                        | 说明              |
| -------------------------- | --------------- |
| `random(min, max)`         | 返回min到max之间的随机数 |
| `abs(value)`               | 绝对值             |
| `min(a, b)`                | 最小值             |
| `max(a, b)`                | 最大值             |
| `int(value)`               | 取整              |
| `distance(x1, y1, x2, y2)` | 两点距离            |
| `angle(x1, y1, x2, y2)`    | 两点角度（弧度）        |
| `cos(angle)`               | 余弦              |
| `sin(angle)`               | 正弦              |

### 38.2 对象表达式

| 表达式                          | 说明       |
| ---------------------------- | -------- |
| `Self.X` / `Self.Y`          | 自身坐标     |
| `Self.Width` / `Self.Height` | 自身尺寸     |
| `Self.UID`                   | 自身UID    |
| `对象.X` / `对象.Y`              | 指定对象坐标   |
| `对象.Width` / `对象.Height`     | 指定对象尺寸   |
| `对象.LayerNumber`             | 对象所在图层索引 |
| `对象.ImagePointX(index)`      | 图像点X坐标   |
| `对象.ImagePointY(index)`      | 图像点Y坐标   |

### 38.3 图层表达式

| 表达式                              | 说明       |
| -------------------------------- | -------- |
| `LayerIndex("图层名")`              | 图层索引     |
| `LayerScale(图层索引)`               | 图层缩放     |
| `LayerToLayerX(源图层, 目标图层, x, y)` | 跨图层坐标转换X |
| `LayerToLayerY(源图层, 目标图层, x, y)` | 跨图层坐标转换Y |

### 38.4 循环表达式

| 表达式                | 说明      |
| ------------------ | ------- |
| `loopindex`        | 当前循环索引  |
| `loopindex("循环名")` | 指定循环的索引 |

### 38.5 时间表达式

| 表达式         | 说明     |
| ----------- | ------ |
| `dt`        | 帧时间（秒） |
| `timescale` | 时间缩放   |
| `time`      | 游戏运行时间 |

***

*笔记将持续更新，记录每次项目变更的格式和结构...*
