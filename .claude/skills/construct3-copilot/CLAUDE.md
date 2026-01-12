# Construct 3 Copilot - 项目规范

本项目是 Construct 3 开发辅助工具，支持事件表 JSON 生成和插件开发指导。

## 参考资料

### 事件表 & 脚本
- 完整示例: @references/examples.md
- JSON 格式规范: @references/clipboard-format.md
- 运行时脚本 API: @references/runtime-api.md
- 完整类型定义: source/scripts/ts-defs/

### 插件开发 (Addon SDK)
- 快速参考: @references/addon-sdk-index.md
- 开发指南: @references/addon-sdk/guide/
- API 参考: @references/addon-sdk/reference/

### 其他
- 中文术语: @references/zh-cn.md
- 详细工具指南: @references/instructions.md

## 核心工作流

### 1. Intent IR 解析

收到用户请求后，先解析为结构化意图 (Schema: @references/intent_schema.json):

```json
{
  "gameplay": ["player movement", "collision damage"],
  "ui": ["score text"],
  "assets": ["Player", "Enemy", "ScoreText"],
  "visual_style": {"palette": ["blue", "red"], "resolution": "32x32"},
  "open_questions": ["得分规则？", "结束条件？"],
  "assumptions": []
}
```

### 2. Clarification 循环

当 `open_questions` 非空时，**必须**先澄清再生成：

- 每次只问一个问题
- 等待用户回答后再继续
- 无法澄清时记录到 `assumptions`

示例问题：
- "得分规则：每击破一块 +1 还是 +10？"
- "需要键盘还是触摸控制？"
- "关卡结束条件是什么？"

### 3. Session Memory

多轮对话时维护记忆：

```
已创建对象: Player, Enemy, ScoreText
已定义变量: Score, Lives, GameState
当前布局: MainLayout
假设: 使用键盘控制
```

用户请求增量修改时，复用已有资源而非重建。

### 4. 强制检索规则 ⚠️

**生成任何 ACE ID 之前，必须先检索确认其存在。禁止凭记忆猜测！**

```bash
# 1. 查询 ACE Schema（确认 ID 存在）
python3 scripts/query_schema.py plugin sprite set-animation
python3 scripts/query_schema.py behavior platform simulate-control
python3 scripts/query_schema.py search <关键词>

# 2. 查询案例库（学习真实用法）
python3 scripts/query_examples.py action set-animation
python3 scripts/query_examples.py condition on-collision
python3 scripts/query_examples.py top actions 20
```

**检索流程**：
1. 识别需要的 ACE 类型（条件/动作/表达式）
2. 用 `query_schema.py` 确认 ACE ID 正确拼写
3. 用 `query_examples.py` 查看真实项目中的参数用法
4. 只使用检索到的 ACE ID，不要发明新的

**常见幻觉陷阱**：
- ❌ `set-angle-toward-position` → 不存在
- ✅ `set-angle` + `angle(x1,y1,x2,y2)` 表达式
- ❌ `move-toward` → 不存在
- ✅ 使用 MoveTo 行为或手动计算

## 输出规范

### JSON 格式要求

- 必须包含 `"is-c3-clipboard-data": true`
- `type` 必须是: events, object-types, layouts, world-instances, event-sheets, conditions, actions
- 字符串参数使用嵌套引号: `"text": "\"Hello\""`
- 比较运算符使用数字: 0=等于, 1=不等于, 2=小于, 3=小于等于, 4=大于, 5=大于等于
- 按键码使用数字: 87=W, 65=A, 83=S, 68=D, 32=Space
- Behavior 动作必须指定 `behaviorType` (使用显示名如 "Platform", "8Direction")
- Variable 必须包含 `comment`, `type`, `initialValue` 字段

### 脚本动作格式

事件表中可以嵌入 JavaScript/TypeScript 脚本块：

```json
{
  "type": "script",
  "language": "javascript",
  "script": ["localVars.result = localVars.a + localVars.b;"]
}
```

- `language`: 必须指定 `"javascript"` 或 `"typescript"`
- `script`: 字符串数组，每行一个元素
- 可用对象: `runtime`, `localVars`, `runtime.objects`, `runtime.globalVars`
- 参考 @references/runtime-api.md 了解完整 API

### 输出前验证

1. 运行 `scripts/validate_output.py '<json>'`
2. 检查所有引用的对象/变量是否已定义
3. 确保 ACE ID 正确 (使用 `scripts/query_schema.py` 验证)

### 交付内容

每次输出必须包含：
- JSON 代码块
- 粘贴位置说明 (Event sheet margin / Project Bar → Object types 等)
- 手动验证步骤 (运行后检查什么)
- 使用的假设列表

## 设计原则

### 状态机设计

- 使用枚举变量管理状态: `GameState` (0=playing, 1=paused, 2=gameover)
- Boolean 使用 `Is*` 前缀: `IsPaused`, `IsInvincible`

### 事件组织

- 按职责分组: Input, Movement, Collision, UI, Reset
- 使用 `eventType: "group"` 组织相关事件
- 生命周期顺序: 初始化 → 运行时循环 → 结束检测 → 清理/重启

### 完整循环原则

输出必须提供可运行的完整循环：
- 控制输入 → 核心机制 → 计分/进度 → 胜负处理 → 重启钩子

如果用户只请求片段，要么明确范围限定，要么补充缺失的脚手架。

## 美术能力边界

本项目**只能**生成占位符级别的几何图形：
- 纯色方块/圆形
- 简单条纹/渐变
- Kenney 风格预设

**不能**生成：
- 专业像素画
- 复杂动画帧
- 写实风格素材

需要美术资源时，使用 `scripts/generate_imagedata.py` 并明确告知用户这是占位符。

## 中文支持

- 支持中文输入和输出
- ACE 术语对照: @references/zh-cn.md
- Intent IR 可使用中文描述，但最终 JSON 必须是英文 ACE ID

## Behavior 映射

behaviorId 与 behaviorType 对照: @references/behavior-names.md
