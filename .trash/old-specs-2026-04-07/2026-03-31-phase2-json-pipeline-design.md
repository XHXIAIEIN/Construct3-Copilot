# Phase 2: JSON 处理管线设计

**Date**: 2026-03-31
**Status**: Approved
**Depends on**: Phase 1.1 (Copilot Core skeleton)
**Blocked by**: None (Clipboard/MCP 服务不可用时走降级)

---

## 1. 核心定位

Phase 2 将 pipeline 从"RAG-augmented chat"升级为**双轨管线**：

- **Q&A 轨**（已有）：自然语言问答 + RAG 知识增强
- **JSON 处理轨**（新增）：检测到 C3 clipboard JSON → 验证 / 分析 / 修改 / 修复

**触发条件**：用户消息中包含 `"is-c3-clipboard-data"` 标记字段的 JSON。

**设计原则**：
- 管线逻辑完整，下游服务不可用时优雅降级
- JSON 检测用确定性规则（正则），不浪费 LLM token
- 验证器是本地轻量版，为 Phase 5 完整 Clipboard 验证器铺路
- LLM 负责理解用户意图和生成修改，验证器负责格式正确性

---

## 2. 管线流程

```
用户消息进入
  │
  ▼
[1] Session 加载/创建（不变）
  │
  ▼
[2] JSON 检测：扫描消息体找 "is-c3-clipboard-data"
  │
  ├─ 未找到 → Q&A 轨（现有逻辑，不变）
  │
  └─ 找到 → JSON 处理轨
      │
      ▼
    [3] 解析：从消息中提取 JSON 块 + 用户附带的自然语言指令
      │
      ▼
    [4] 本地验证：格式检查 + 已知坑位检测（不依赖外部服务）
      │
      ▼
    [5] RAG 检索 + ACE 验证：检索相关 ACE 文档，同时验证 ACE ID
      │
      ▼
    [6] LLM 理解：结合验证结果 + RAG 上下文 + 用户指令
      │  决定操作类型：分析 / 修改 / 修复
      │
      ▼
    [7] 执行：LLM 生成修改后的 JSON 或分析报告
      │
      ▼
    [8] 输出验证：如果 LLM 输出了 JSON，再跑一次验证
      │
      ▼
    [9] 交付：返回结果
         · 分析 → type=direct_answer, message=分析报告
         · 修改/修复 → type=generation, data.clipboard_json=修改后的JSON
```

---

## 3. 支持的操作

| 操作 | 触发方式 | 输出 |
|------|---------|------|
| **验证** | 用户贴 JSON（无额外指令，或说"检查一下"） | 验证报告：错误 + 警告 + 建议 |
| **分析** | "这段 JSON 做了什么"、"解释一下" | 自然语言解释事件逻辑 |
| **修改** | "把速度改成 200"、"加一个双跳" | 修改后的完整 JSON |
| **修复** | "帮我修一下"、验证发现错误后自动建议修复 | 修复后的完整 JSON + 修复说明 |

操作类型由 LLM 根据用户指令 + 验证结果综合判断，不需要硬编码分类。

---

## 4. 组件设计

### 4.1 JSON 检测器 (`orchestrator/detector.py`)

**职责**：从用户消息中检测并提取 C3 clipboard JSON。

```python
@dataclass
class DetectionResult:
    found: bool
    clipboard_json: dict | None      # 解析后的 JSON
    clipboard_type: str | None       # "events" | "object-types" | "layouts" | ...
    user_instruction: str             # JSON 之外的自然语言文本
    raw_json_str: str | None          # 原始 JSON 字符串（用于回传）
```

**检测逻辑**：
1. 正则扫描消息中的 JSON 块（`{...}` 匹配，支持嵌套）
2. 逐个尝试 `json.loads()`
3. 检查是否有 `"is-c3-clipboard-data": true`
4. 提取 `type` 字段确定剪贴板类型
5. 消息中 JSON 之外的文本作为 `user_instruction`

**边界情况**：
- 消息中有多个 JSON 块 → 只取第一个包含 `is-c3-clipboard-data` 的
- JSON 格式错误 → `found=False`，走 Q&A 轨（LLM 可能能帮忙修 JSON 语法）
- JSON 合法但不是 clipboard 格式 → `found=False`

### 4.2 JSON 验证器 (`orchestrator/validator.py`)

**职责**：对 clipboard JSON 做本地验证，输出结构化报告。

```python
@dataclass
class ValidationIssue:
    level: str          # "error" | "warning" | "suggestion"
    code: str           # 机器可读代码，如 "EMPTY_PARAMS"
    message: str        # 人可读描述
    path: str           # JSON 路径，如 "events[2].actions[0].parameters"

@dataclass
class ValidationReport:
    passed: bool                    # 无 error 级别问题
    issues: list[ValidationIssue]
    summary: str                    # 一句话总结
```

**三层验证**：

1. **结构验证** — 本地规则，不依赖外部服务
   - 顶层：`is-c3-clipboard-data: true` 存在、`type` 合法
   - events：`eventType` 枚举检查、block 必须有 conditions 或 actions
   - objects：`instanceVariables` 是数组不是对象
   - 通用：SID 唯一性

2. **已知坑位检测** — 从 legacy `c3-event-sheet-dev-notes-raw.md` 的 16+ 已知问题提炼
   - 空 `parameters` 对象应省略（不是 `{}`）
   - 触发型条件不能出现在 children 中
   - 每个事件最多一个触发型条件
   - `behaviorType` 应使用显示名不是 ID
   - 变量声明必须有 `comment` 字段（可以是空字符串）
   - 颜色值用 `[0-1]` 浮点 RGBA，不是 0-255

3. **ACE 验证** — 依赖 RAG 服务（不可用时跳过，标记 warning）
   - 检查 ACE ID 是否存在于对应 plugin/behavior
   - 检查参数数量和名称是否匹配
   - 降级：RAG 不可用时跳过此层，在 report 中注明 "ACE validation skipped: RAG unavailable"

### 4.3 JSON 处理 Prompt (`llm/prompts/clipboard.py`)

**专用 system prompt**，注入以下上下文：

```
[1] 角色定义：C3 clipboard JSON 专家
[2] 验证报告（如果有问题）
[3] RAG 检索的 ACE 文档（如果有）
[4] 用户的 clipboard JSON
[5] 用户的自然语言指令
```

**LLM 输出格式约束**：
- 分析模式：纯文本回答
- 修改/修复模式：必须输出完整的 clipboard JSON（不是 diff），用 ```json 代码块包裹
- 修改时附带简要说明改了什么

### 4.4 管线主体 (`orchestrator/pipeline.py` 扩展)

在 `Pipeline` 类中：

- `__init__` 增加 `clipboard: ClipboardClient = None` 参数（降级可选）
- `process()` 在 Session 创建后、RAG 检索前，先调用 detector
- 检测到 JSON → 走 `_process_json()` 分支
- 未检测到 → 走现有 Q&A 逻辑（不变）

```python
async def _process_json(self, session, detection: DetectionResult) -> ChatResponse:
    # [4] 本地验证（结构 + 坑位，不依赖外部服务）
    report = self.validator.validate_local(detection.clipboard_json)

    # [5] RAG 检索 + ACE 验证
    rag_query = self._build_rag_query_from_json(detection.clipboard_json)
    rag_context, rag_used = await self._fetch_rag_context(rag_query)
    ace_issues = await self.validator.validate_ace(detection.clipboard_json, self.rag)
    report.issues.extend(ace_issues)
    report.passed = report.passed and not any(i.level == "error" for i in ace_issues)

    # [6-7] LLM 调用
    system_prompt = build_clipboard_prompt(
        clipboard_json=detection.clipboard_json,
        validation_report=report,
        rag_context=rag_context,
        user_instruction=detection.user_instruction,
    )
    messages = [{"role": "system", "content": system_prompt}, *session.messages]
    reply = await self.llm.chat(messages)

    # [8] 如果 LLM 回复中包含 JSON，提取并再验证
    output_json = extract_json_from_reply(reply)
    output_validation = None
    if output_json:
        output_validation = self.validator.validate(output_json)

    # [9] 交付
    if output_json:
        return ChatResponse(
            session_id=session.session_id,
            type="generation",
            message=reply,  # 包含说明文字
            data=GenerationData(
                delivery="clipboard",
                clipboard_json=output_json,
                validation=output_validation.to_dict(),
            ),
            modules_used=[...],
        )
    else:
        return ChatResponse(
            session_id=session.session_id,
            type="direct_answer",
            message=reply,
            modules_used=[...],
        )
```

---

## 5. 数据模型变动

### `schemas/api.py` 扩展

`GenerationData` 增加 `input_validation` 字段，用于返回输入 JSON 的验证报告：

```python
class GenerationData(BaseModel):
    delivery: Literal["clipboard", "mcp"]
    clipboard_json: Optional[dict] = None
    validation: Optional[dict] = None           # 输出 JSON 的验证结果
    input_validation: Optional[dict] = None     # 输入 JSON 的验证结果
    metadata: Optional[dict] = None
```

---

## 6. RAG 集成

JSON 处理轨的 RAG 查询策略：

- 从 clipboard JSON 中提取所有 `objectClass` + `behaviorType` + ACE ID
- 构建查询：`"<plugin> <behavior> <ace_id>"` 的组合
- 用于两个目的：
  1. 验证器的 ACE 验证层
  2. LLM prompt 的知识注入（让 LLM 知道正确的参数格式）

---

## 7. 文件变动清单

```
新增：
  src/orchestrator/detector.py        # clipboard JSON 检测 + 提取
  src/orchestrator/validator.py       # 本地 JSON 验证（结构 + ACE + 坑位）
  src/llm/prompts/clipboard.py       # JSON 处理专用 prompt
  tests/test_detector.py             # 检测器测试
  tests/test_validator.py            # 验证器测试
  tests/test_pipeline_json.py        # JSON 处理管线集成测试

修改：
  src/orchestrator/pipeline.py       # 加入 JSON 检测分支 + _process_json()
  src/schemas/api.py                 # GenerationData 增加 input_validation
```

---

## 8. 降级策略

| 模块不可用 | 影响 | 降级行为 |
|-----------|------|---------|
| RAG | ACE 验证无法执行 | 跳过 ACE 验证层，report 中标注；LLM 依赖自身知识 |
| LLM | 无法理解用户意图 | 返回 error，但仍可返回验证报告（纯本地） |
| Clipboard 服务 | Phase 2 本来就不调 | 无影响 |
| MCP | Phase 2 本来就不调 | 无影响 |

**特殊降级**：LLM 不可用但 JSON 验证可以独立运行 — 返回 `type="direct_answer"`，message 为验证报告的文本版本。

---

## 9. Phase 2 不含（后续 Phase 实现）

| 功能 | 计划阶段 | 说明 |
|------|---------|------|
| 从零生成 clipboard JSON | Phase 5 | Clipboard 服务负责，接收精确 IR |
| MCP 直写项目 | Phase 3+ | construct3-mcp 桥接实现 |
| Intent IR 生成 | Phase 5 | 随 Clipboard 服务一起上线 |
| 完整 JSON Schema 验证 | Phase 5 | Clipboard 服务内置完整验证器 |
| 意图理解 → 澄清循环 → IR 精化 | Phase 5 | 完整编排工作流 |
