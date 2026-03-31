# Construct 3 Copilot 生态整合设计

**Date**: 2026-03-31
**Status**: Draft
**Supersedes**: `docs/specs/2026-03-13-rag-integration-design.md`

---

## 1. 核心理念

Copilot 从"全能单体"重构为"编排服务 + 多前端"架构。所有知识、生成能力、项目操作能力均来自外部模块，通过标准接口热拔插接入。Copilot Core 是统一管道，多种前端共享同一套编排逻辑。

**设计原则：**
- **零知识** — Copilot 不持有 ACE 数据、文档、示例、SDK 参考
- **零生成** — Copilot 不直接生成 JSON，委托给 Clipboard 服务
- **LLM 集中** — 所有 LLM 调用归 Copilot Core 管，下游模块（Clipboard/RAG）不依赖大模型做核心逻辑
- **统一管道** — 多种前端（Skill / Web UI / 编辑器插件 / Bridge）共享同一个编排 API
- **热拔插** — 任何模块不可用时 Copilot 降级运行，不崩溃
- **双层接口** — FastAPI HTTP 为核心服务层，MCP 为 AI 助手接入层

---

## 2. 生态架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端层 (多种交互形态)                      │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐         │
│  │Claude Code│ │ Web Chat │ │ C3 Editor │ │WebSocket │  ...    │
│  │  Skill   │ │   UI     │ │  Plugin   │ │ Bridge   │         │
│  └────┬─────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘         │
│       │             │             │             │                │
│       └──────┬──────┴──────┬──────┘             │                │
│              │  HTTP REST  │   WebSocket ────────┘                │
│              ▼             ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Copilot Core (:8767)  — 统一编排管道          │   │
│  │                                                          │   │
│  │  · LLM 调用 (Claude API / Ollama / OpenAI)               │   │
│  │  · Session 管理（多轮对话、对象/变量追踪）                  │   │
│  │  · 意图理解 → Clarification → IR 精化                     │   │
│  │  · 输出路由（construct3-mcp vs Clipboard）                │   │
│  │  · 模块健康检查 + 降级策略                                 │   │
│  │                                                          │   │
│  │  不做：                                                   │   │
│  │  · 不持有 ACE schema / 文档 / 示例数据                     │   │
│  │  · 不直接生成 C3 JSON（委托 Clipboard）                    │   │
│  │  · 不做 ACE 验证（委托 Clipboard 或 RAG）                  │   │
│  └──────┬──────────┬──────────┬──────────────────────────────┘   │
│         │          │          │                                   │
│      HTTP        HTTP      MCP (stdio)                           │
│         │          │          │                                   │
│         ▼          ▼          ▼                                   │
│  ┌───────────┐ ┌──────────┐ ┌──────────────┐                    │
│  │ C3-RAG    │ │C3-Clip   │ │construct3-mcp│                    │
│  │ :8765     │ │:8766     │ │(liauw-media) │                    │
│  └───────────┘ └──────────┘ └──────────────┘                    │
│       ▲                                                          │
│  数据源 ingest                                                    │
│       │                                                          │
│  ┌────┴─────────────────┐                                       │
│  │ Construct3-Manual    │  (含 Addon-SDK 文档)                   │
│  │ Construct-Example-   │                                       │
│  │   Projects (524个)   │                                       │
│  │ Construct-Addon-SDK  │                                       │
│  └──────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 模块清单

### 3.1 Construct3-Copilot（本仓库，清空重建）

**定位：** Construct 3 语义理解引擎 + 编排服务（FastAPI :8767）+ 多前端

**核心技能：语义理解** — Copilot 的根本价值是理解用户用自然语言描述的游戏需求，将模糊的"做一个平台跳跃游戏"精确翻译为 Construct 3 的领域语言（哪些插件、哪些行为、哪些 ACE、什么参数）。其他一切（检索、生成、写入）都是手脚，语义理解是大脑。

Copilot 分为两层：**Core**（后端编排服务）和 **Frontends**（多种交互形态）。

#### 3.1.1 Copilot Core — 编排服务

FastAPI 应用，所有前端共享同一套编排逻辑。

**仓库结构：**
```
Construct3-Copilot/
├── src/
│   ├── api.py                   # FastAPI 主入口
│   ├── config.py                # 配置（端口、LLM、模块地址）
│   ├── llm/
│   │   ├── client.py            # LLM 统一客户端
│   │   ├── providers/
│   │   │   ├── claude.py        # Claude API (Anthropic SDK)
│   │   │   ├── openai.py        # OpenAI API
│   │   │   └── ollama.py        # Ollama 本地模型
│   │   └── prompts/
│   │       ├── system.py        # 系统提示词
│   │       ├── intent.py        # 意图理解提示词
│   │       ├── clarify.py       # Clarification 提示词
│   │       └── refine.py        # IR 精化提示词
│   ├── orchestrator/
│   │   ├── session.py           # Session 管理（多轮对话状态）
│   │   ├── pipeline.py          # 编排管线（意图→澄清→精化→路由→执行）
│   │   ├── router.py            # 输出路由（construct3-mcp vs Clipboard）
│   │   └── degradation.py       # 降级策略
│   ├── modules/
│   │   ├── rag_client.py        # RAG HTTP 客户端
│   │   ├── clipboard_client.py  # Clipboard HTTP 客户端
│   │   ├── mcp_bridge.py        # construct3-mcp 调用桥接
│   │   └── health.py            # 模块健康检查
│   └── schemas/
│       ├── intent_ir.py         # Intent IR 数据模型 (Pydantic)
│       ├── session.py           # Session 数据模型
│       └── api.py               # API 请求/响应模型
├── frontends/
│   ├── cli/                     # 终端对话前端 (P0)
│   │   ├── __main__.py          # 入口 (python -m c3copilot)
│   │   ├── repl.py              # readline 交互循环
│   │   ├── display.py           # 输出格式化（JSON 高亮、状态栏）
│   │   └── clipboard.py         # 系统剪贴板写入
│   ├── skill/                   # Claude Code / Codex Skill 前端 (P0)
│   │   ├── CLAUDE.md            # Skill 主指令
│   │   ├── SKILL.md             # 触发关键词
│   │   └── references/
│   │       ├── workflow.md      # 编排工作流说明
│   │       └── intent-schema.json
│   └── web/                     # Web Chat UI / C3 Editor Plugin (P2, 后续)
│       └── ...
├── tests/
│   ├── test_pipeline.py         # 编排管线测试
│   ├── test_router.py           # 路由测试
│   ├── test_degradation.py      # 降级测试
│   └── test_api.py              # API 端点测试
├── requirements.txt
└── README.md
```

**不包含：**
- `data/` 目录（无 schemas、无 project_analysis）
- `source/` 目录（无 CSV、无 TypeScript 定义）
- 重复的 addon-sdk / manual / examples 引用文档
- JSON 生成逻辑（在 Clipboard 仓库）

**API 端点：**
```
GET  /health                     # Core + 各模块健康状态
POST /chat                       # 主对话端点（前端统一入口）
POST /chat/stream                # SSE 流式对话
GET  /session/{id}               # 获取会话状态
DELETE /session/{id}             # 清除会话

WebSocket /ws                    # WebSocket 双向通信（Bridge/实时前端）
```

**POST /chat 请求体：**
```json
{
  "session_id": "uuid-or-null",
  "message": "给我做一个平台跳跃游戏，要双跳",
  "context": {
    "has_local_project": true,
    "project_path": "/path/to/my.c3proj"
  }
}
```

**POST /chat 响应体：**
```json
{
  "session_id": "abc-123",
  "type": "clarification | generation | direct_answer",
  "message": "玩家需要墙跳吗？落地后跳跃次数怎么重置？",
  "data": null,
  "modules_used": ["rag"]
}
```

**生成完成时的响应：**
```json
{
  "session_id": "abc-123",
  "type": "generation",
  "message": "已生成平台跳跃移动系统",
  "data": {
    "delivery": "clipboard",
    "clipboard_json": { "is-c3-clipboard-data": true, ... },
    "validation": { "passed": true, "warnings": [] },
    "metadata": { "objects": 2, "events": 5, "behaviors": ["Platform"] }
  },
  "modules_used": ["rag", "clipboard"]
}
```

#### 3.1.2 前端层

所有前端都是 Copilot Core 的薄客户端，只负责 UI 交互，不含编排逻辑。

| 前端 | 接口 | 交互方式 | 优先级 |
|------|------|---------|-------|
| **CLI (终端纯文字)** | HTTP → Core /chat | 终端对话，类似 Claude Code 交互体验 | P0 (首发) |
| **Claude Code Skill** | HTTP → Core /chat | Skill 触发 → 调 Core API → 返回结果到对话 | P0 |
| **Web Chat UI / C3 Editor Plugin** | HTTP + WebSocket | 浏览器/编辑器内嵌面板（本质相同，只是宿主不同） | P2 (后续) |
| **WebSocket Bridge** | WebSocket → Core /ws | 无头模式，供第三方工具集成 | P3 (后续) |

**CLI 终端前端（P0，首发）：**

类似 Claude Code 的终端对话体验，纯文字交互：

```bash
$ c3copilot
🎮 Construct 3 Copilot v2.0
   RAG: ✓ online   Clipboard: ✓ online   MCP: ✗ no project

> 做一个平台跳跃游戏，要双跳

  需要确认几个细节：
  1. 玩家落地后重置跳跃次数，还是只在地面时才能起跳？
  2. 需要墙跳吗？

> 落地重置，不要墙跳

  ✓ 已生成 PlayerMovement 事件表 (2 objects, 5 events)
  
  [JSON 已复制到剪贴板]  或  按 Enter 查看完整 JSON
```

**实现：** Python CLI 应用，调 Core `/chat` 端点，readline 交互，支持 `--project /path` 指定 C3 项目路径。

**Claude Code Skill（P0）：**

Skill 作为薄前端，调用 Copilot Core API。存在两种模式：
1. **Core API 模式** — Skill 调 Core 服务（Core 自行调 LLM API，完整编排能力）
2. **宿主直连模式** — Core 不在线时，Skill 提示词引导宿主 LLM 直接编排（降级，能力受限）

由 Skill 自动检测 Core 可用性决定。

#### 3.1.3 编排工作流

```
前端 → POST /chat
  │
  ▼
[1] Session 加载/创建
  │  · 新对话 → 创建 Session
  │  · 续接 → 加载历史上下文
  │
  ▼
[2] 意图理解                          ← LLM 调用
  │  · 解析用户自然语言
  │  · 调用 RAG /search 获取相关 ACE   ← HTTP (无 LLM)
  │  · 生成粗粒度 Intent IR
  │
  ▼
[3] Clarification 循环                ← LLM 调用
  │  · 根据 Intent IR 判断是否有歧义
  │  · 缺失信息 → 返回 type=clarification 给前端
  │  · 用户回答后再次进入 [2]
  │  · confidence 足够 → 进入下一步
  │
  ▼
[4] IR 精化                           ← LLM 调用（核心步骤）
  │  · 将粗粒度 IR 细化为 Clipboard 可接受的精确 IR
  │  · 每个 event 的 conditions/actions 精确到 ACE ID + 参数
  │  · 所有对象、变量、行为完整声明
  │
  ▼
[5] 输出路由判断
  │  ├─ has_local_project=true → construct3-mcp 直写 (MCP, 无 LLM)
  │  └─ has_local_project=false → Clipboard /generate (HTTP, 无 LLM)
  │
  ▼
[6] 执行                              ← 下游模块，确定性执行
  │  · 调用对应模块，传入精确 IR
  │  · 收集结果
  │
  ▼
[7] 交付                              → 返回给前端
     · type=generation
     · 附带 clipboard_json 或 mcp 操作结果
```

#### 3.1.4 降级策略

| 模块不可用 | 降级行为 |
|-----------|---------|
| RAG 不可用 | 跳过知识检索，依赖 LLM 自身知识 + 提示词 |
| Clipboard 不可用 | 无法生成剪贴板 JSON，引导用户使用 construct3-mcp |
| construct3-mcp 不可用 | 无法直写项目，退回剪贴板 JSON 模式 |
| LLM 不可用 | 服务不可用，返回错误 |
| 全部不可用 | 返回错误，告知用户启动所需服务 |

---

### 3.2 Construct3-RAG（已有仓库）

**定位：** 知识检索基础设施，FastAPI HTTP 服务

**现状：** 功能完整，:8765 运行，3 层检索（精确→关键词→语义）

**整合需改动：**

1. **数据源扩展** — ingest 管线增加：
   - Construct3-Manual（手册 markdown）→ 已有 `markdown_parser.py`
   - Construct-Example-Projects（524 个项目）→ 已有 `examples_parser.py`
   - Construct-Addon-SDK（schema JSON + 示例代码）→ 新增 parser
   
2. **MCP Adapter 层（可选）** — 薄壳映射：
   ```
   POST /search     → MCP tool: c3_search
   POST /decompose  → MCP tool: c3_decompose
   GET  /health     → MCP tool: c3_rag_health
   ```

3. **无需改动的部分：**
   - 核心检索逻辑
   - API 接口定义
   - 现有数据结构

**API 端点（不变）：**
```
GET  /health              # 健康检查
GET  /playground           # Web UI
POST /search              # 主检索端点
POST /decompose           # 意图分解（计划中）
```

---

### 3.3 Construct3-Clipboard（新建仓库）

**定位：** Schema 驱动的 C3 剪贴板 JSON 生成服务，FastAPI HTTP

**核心理念：规则即代码，Schema 即文档。**

不维护任何 markdown 格式的"注意事项"或"易错点"文档。所有格式规则、参数约束、结构要求全部编码为 JSON Schema + Python 代码。5000 行的踩坑笔记变成 50 个验证函数和 200 个测试用例。

**职责边界：**
- 接收精确的 Intent IR（由 Copilot Core + LLM 生成）
- **从 Schema 驱动**确定性映射为 C3 剪贴板 JSON（纯代码，无 LLM）
- 生成即合规——生成器从 schema 构建 JSON，不可能产出不合法的结构
- 验证外部 JSON（用户提交的或其他工具产出的）
- 生成占位图（彩色方块 PNG base64）

**不负责：**
- 不做意图理解（Copilot 的事）
- 不做知识检索（RAG 的事）
- 不操作 C3 项目文件（construct3-mcp 的事）
- 不调用任何 LLM — 输入确定则输出确定，100% 可复现
- **不维护文档形式的规则** — 规则在代码和 schema 里，不在 .md 里

#### Schema 分层

```
schemas/
├── clipboard.schema.json        # Layer 1: 剪贴板顶层结构
│   · is-c3-clipboard-data: true (必需)
│   · type 枚举: events | object-types | layouts | world-instances | event-sheets
│   · 每种 type 对应的 items 结构定义
│
├── events.schema.json           # Layer 2: 事件结构
│   · eventType 枚举: block | variable | comment | group | function-block
│   · block: conditions[] + actions[] + children[]?
│   · variable: name + type + initialValue + comment (必需)
│   · function-block: functionName + functionReturnType + functionParameters[]
│   · 结构规则（代码强制执行）：
│     - 无参数时省略 parameters 字段（不是空对象）
│     - 触发型条件不能出现在 children 中
│     - 每个事件最多一个触发型条件
│
├── objects.schema.json          # Layer 2: 对象类型结构
│   · instanceVariables: 数组（不是 {items,subfolders} 对象）
│   · behaviorTypes: 数组
│   · effectTypes: 数组
│   · Sprite 必需 animations.items[].frames[]
│
├── layouts.schema.json          # Layer 2: 布局结构
│   · layers[].instances[] 世界实例结构
│   · world: x,y,width,height,color([0-1] RGBA)
│
└── (Layer 3: ACE 参数 — 从 RAG 动态获取，不在本仓库维护)
    · 每个 plugin/behavior 的合法 ACE ID
    · 每个 ACE 的参数名、参数类型
    · behaviorId → behaviorType 映射
    · 已废弃 ACE 的替代方案
```

**Schema 如何使用：**

```python
# 生成器从 schema 构建 — 产出即合规
def build_action(id: str, object_class: str, params: dict = None, **kwargs) -> dict:
    node = {"id": id, "objectClass": object_class, "sid": generate_sid()}
    if params:  # schema 规则：无参数时省略字段
        node["parameters"] = params
    if kwargs.get("behavior_type"):
        node["behaviorType"] = kwargs["behavior_type"]  # 用显示名，不是 ID
    return node

# 验证器用 schema 检查 — 外部 JSON 也能校验
def validate(json_data: dict) -> ValidationResult:
    errors = []
    errors += validate_against_schema(json_data, "clipboard.schema.json")
    errors += validate_structural_rules(json_data)  # 触发条件嵌套、参数省略等
    errors += validate_ace_ids(json_data, rag_client)  # 调 RAG 验证 ACE
    return ValidationResult(passed=len(errors) == 0, errors=errors)
```

**仓库结构：**
```
Construct3-Clipboard/
├── src/
│   ├── api.py                   # FastAPI 主入口
│   ├── config.py                # 配置
│   ├── schemas/                 # JSON Schema 定义（单一真相源）
│   │   ├── clipboard.schema.json
│   │   ├── events.schema.json
│   │   ├── objects.schema.json
│   │   ├── layouts.schema.json
│   │   └── intent_ir.schema.json  # IR 输入格式定义
│   ├── generator/               # Schema 驱动的生成器
│   │   ├── builder.py           # 底层节点构建（强制 schema 约束）
│   │   ├── events.py            # 事件表生成
│   │   ├── objects.py           # 对象类型生成
│   │   ├── layouts.py           # 布局生成
│   │   ├── instances.py         # 世界实例生成
│   │   └── renderer.py          # IR → JSON 渲染入口
│   ├── validator/               # Schema 驱动的验证器
│   │   ├── schema_validator.py  # JSON Schema 结构验证
│   │   ├── structural_rules.py  # 语义规则（触发条件嵌套、参数省略等）
│   │   └── ace_validator.py     # ACE ID 验证（调 RAG）
│   └── imagedata/
│       └── generator.py         # 占位图生成
├── schemas/                     # Schema 文件（供外部工具引用）
│   └── (同 src/schemas/ 的符号链接或构建产物)
├── errors/                          # 错题本
│   ├── cases/
│   │   └── errors.jsonl             # 所有错误案例（追加写入）
│   └── pending/                     # 待处理案例
├── tests/
│   ├── test_schema_compliance.py    # 每个 schema 规则对应测试
│   ├── test_structural_rules.py     # 每条结构规则对应测试
│   ├── test_known_pitfalls.py       # 已知踩坑案例（从错题本转化）
│   ├── examples/                    # 已验证的端到端输入输出对
│   │   ├── breakout/
│   │   ├── platformer/
│   │   └── shooter/
│   └── fixtures/
│       ├── valid/                   # 合法 JSON 样本
│       └── invalid/                 # 非法 JSON 样本（从错题本提取）
├── scripts/
│   ├── import_errors.py             # 从外部笔记批量导入错题
│   └── generate_tests.py            # 从错题本生成测试用例
├── requirements.txt
└── README.md
```

**API 端点：**
```
GET  /health                     # 健康检查
POST /generate                   # 主生成端点
POST /validate                   # 验证已有 JSON
POST /templates                  # 列出可用模板
GET  /format-spec                # 返回剪贴板格式说明
```

**POST /generate 请求体：**
```json
{
  "intent_ir": {
    "type": "event_sheet",
    "description": "8方向移动 + 碰撞检测",
    "objects": ["Player", "Wall"],
    "behaviors": [{"object": "Player", "type": "8Direction"}],
    "events": [...]
  },
  "ace_context": {
    "actions": [...],
    "conditions": [...],
    "expressions": [...]
  },
  "options": {
    "include_imagedata": true,
    "language": "zh-CN"
  }
}
```

**POST /generate 响应体：**
```json
{
  "success": true,
  "clipboard_json": { "is-c3-clipboard-data": true, ... },
  "validation": {
    "passed": true,
    "warnings": [],
    "checklist": {"ace_ids_valid": true, "format_correct": true, ...}
  },
  "metadata": {
    "objects_created": 2,
    "events_created": 3,
    "behaviors_used": ["8Direction"]
  }
}
```

**端口：** `:8766`（与 RAG 的 :8765 相邻）

**ACE 验证数据来源：** 调用 RAG 的 `/search` 端点验证 ACE ID，不自行维护 ACE 数据副本。如果 RAG 不可用，跳过 ACE 验证但在 warnings 中标注。

#### 错题本系统 (Error Notebook)

**目的：** 每个错误只犯一次。发现的非法 JSON 自动收录，驱动 schema 规则演进。

**数据结构：**
```
错题本/
├── cases/                           # 每个错误一个 JSONL 条目
│   └── errors.jsonl                 # 追加写入，不手动编辑
└── pending/                         # 待处理：已收录但尚未转化为规则
    └── (自动生成的待修复案例)
```

**单条错题格式：**
```json
{
  "id": "ERR-2026-0042",
  "timestamp": "2026-03-31T14:30:00Z",
  "source": "user_report | validation_catch | c3_editor_crash",
  "input_ir": { ... },
  "bad_json": { ... },
  "error": {
    "type": "structural | ace_invalid | parameter_type | c3_crash",
    "message": "TypeError: expected string",
    "location": "events[2].actions[0].parameters"
  },
  "root_cause": "空 parameters 对象应省略",
  "fix": "生成器 build_action() 已修复：params 为空时不输出字段",
  "status": "pending | rule_added | test_added | resolved",
  "rule_ref": "structural_rules.py:no_empty_parameters",
  "test_ref": "test_known_pitfalls.py::test_empty_parameters_omitted"
}
```

**工作流：**

```
错误发生
  │
  ▼
[1] 收录                              ← 自动/手动
  │  POST /errors/report 或 CLI
  │  写入 cases/errors.jsonl
  │  status = "pending"
  │
  ▼
[2] 分析                              ← 人工或辅助脚本
  │  确定 root_cause
  │  判断属于哪层 schema 规则
  │
  ▼
[3] 修复                              ← 开发者
  │  ├─ 更新 schema（如果是结构规则缺失）
  │  ├─ 更新生成器（如果是生成逻辑问题）
  │  └─ 更新验证器（如果是检查遗漏）
  │
  ▼
[4] 加固                              ← 自动化
  │  ├─ bad_json 复制到 tests/fixtures/invalid/
  │  ├─ 生成对应测试用例
  │  └─ 确保验证器能拦截、生成器不再产出
  │
  ▼
[5] 关闭
     status = "resolved"
     rule_ref + test_ref 填写完毕
```

**API 端点：**
```
POST /errors/report              # 提交错误样本
GET  /errors/pending             # 查看待处理错题
GET  /errors/stats               # 错误分类统计
```

**收录来源：**

| 来源 | 触发方式 | 说明 |
|------|---------|------|
| **验证器拦截** | 自动 | `/validate` 发现非法 JSON 时自动收录 |
| **C3 编辑器崩溃** | 用户上报 | 用户粘贴后编辑器报错，通过 `/errors/report` 提交 |
| **Copilot 反馈** | 自动 | Core 调 Clipboard 生成后再验证，不一致时自动收录 |
| **手动导入** | CLI | 从外部笔记、issue 等批量导入已知问题 |

**与测试系统的关系：**

```
错题本                          测试系统
cases/errors.jsonl    →    tests/fixtures/invalid/   (错误样本)
                      →    tests/test_known_pitfalls.py (回归测试)
                      →    每条 resolved 的错题至少对应 1 个测试用例
```

**指标：**
- `pending` 数量 = 技术债（越少越好）
- `resolved` / `total` = 规则覆盖率
- 同一 `root_cause` 出现 >1 次 = 规则没修对，需要回溯

**初始导入：** 从 `docs/references/c3-event-sheet-dev-notes-raw.md` 的 16+ 个易错点批量导入为初始错题，作为 schema 设计的起点。

---

### 3.4 construct3-mcp（liauw-media，外部仓库）

**定位：** C3 项目文件直接操作，MCP Server (stdio)

**现状：** 29 个工具，278 个测试，v1.6.0

**Copilot 使用方式：**
- 在 `.mcp.json` 中注册，指向用户本地的 C3 项目目录
- Copilot 通过 AI 宿主的 MCP 调用能力使用
- 主要用于"有本地项目"场景下的直接写入

**常用工具：**
```
# 查询
list_objects, list_event_sheets, list_layouts, project_summary

# 写入
create_object, add_instance_variable, add_behavior
create_event_sheet, insert_event
create_layout, add_layout_instance

# 分析
event_sheet_hierarchy, map_functions, track_object_dependencies
```

**无需改动** — 作为外部依赖原样使用。

---

### 3.5 数据源仓库（不暴露独立接口）

以下仓库作为 RAG 的 ingest 数据源，不直接对 Copilot 暴露接口：

| 仓库 | 内容 | RAG ingest 方式 |
|------|------|----------------|
| **Construct3-Manual** | C3 手册 + Addon-SDK 文档 (markdown) | `markdown_parser.py` → Qdrant |
| **Construct-Example-Projects** | 524 个示例项目 | `examples_parser.py` → Qdrant |
| **Construct-Addon-SDK** | plugin/behavior/effect SDK schemas | 新增 `addon_parser.py` → Qdrant |

**ingest 触发：**
- 手动：`python scripts/init.py --sources manual,examples,sdk`
- 自动：GitHub Action 定期拉取更新（RAG 已有 weekly update workflow）

---

## 4. 接口分层策略

```
┌─────────────────────────────────────────┐
│         MCP 适配层（AI 助手接入）          │
│                                         │
│  c3-mcp-gateway (可选的统一入口)          │
│  · c3_search     → RAG /search          │
│  · c3_decompose  → RAG /decompose       │
│  · c3_generate   → Clipboard /generate  │
│  · c3_validate   → Clipboard /validate  │
│                                         │
│  construct3-mcp (liauw-media, 独立)      │
│  · 29 个项目操作工具                      │
│                                         │
├─────────────────────────────────────────┤
│         HTTP 服务层（核心）                │
│                                         │
│  Construct3-RAG      :8765              │
│  Construct3-Clipboard :8766             │
│                                         │
│  · 任何客户端可调用                       │
│  · 自带 /playground UI                   │
│  · 可独立部署和测试                       │
└─────────────────────────────────────────┘
```

**c3-mcp-gateway** 是可选的——如果 Copilot 作为 Skill 运行在 Claude Code 中，可以通过 scripts 直接调 HTTP；如果需要让其他 MCP 客户端（Cursor 等）也能用，再加 gateway。

---

## 5. LLM 架构

### 原则：LLM 调用归 Copilot，下游模块确定性执行

```
┌─────────────────────────────────────────────────┐
│  Copilot Core (:8767)                           │
│  · LLM 客户端 (Claude API / OpenAI / Ollama)    │
│  · 意图理解、Clarification、编排决策              │
│  · 将模糊描述 → 精确 Intent IR                   │
│  · 所有需要"思考"的环节集中在这里                  │
├────────────┬────────────────┬────────────────────┤
│ RAG        │ Clipboard      │ construct3-mcp     │
│ 无 LLM     │ 无 LLM         │ 无 LLM             │
│ 关键词+向量 │ 纯模板引擎      │ 确定性读写          │
│ (jieba/    │ IR → JSON      │                    │
│  embedding)│ 代码生成        │                    │
└────────────┴────────────────┴────────────────────┘
```

### 各模块 LLM 依赖

| 模块 | LLM | 说明 |
|------|-----|------|
| **Copilot Core** | Claude API / OpenAI / Ollama（可配置） | 所有推理、理解、决策。Core 自行管理 LLM 调用，前端不关心用的是哪个模型 |
| **RAG** | 无 | 检索用关键词匹配 + 向量相似度，不需要 LLM 推理。原 Tier-3 的 Ollama 意图分类改为规则/关键词方案 |
| **Clipboard** | 无 | 纯模板引擎 + 代码生成。接收精确的 Intent IR，确定性映射为 C3 剪贴板 JSON。无推理、无生成、无歧义 |
| **construct3-mcp** | 无 | 确定性文件读写 |

### LLM Provider 配置

Copilot Core 通过 `config.py` 配置 LLM provider，支持切换：

```python
# .env
LLM_PROVIDER=claude          # claude | openai | ollama
LLM_MODEL=claude-sonnet-4-6  # 具体模型
LLM_API_KEY=sk-...           # API key（Ollama 不需要）
LLM_BASE_URL=                # 自定义端点（可选）
```

**推荐配置：**
- **开发/测试**: Ollama + qwen2.5:7b（免费，本地）
- **生产**: Claude API + claude-sonnet-4-6（质量最高）
- **预算有限**: OpenAI + gpt-4o-mini

### Intent IR 的精度要求

因为 Clipboard 无 LLM，Copilot 输出的 Intent IR 必须足够精确，不能有歧义：

```jsonc
// ❌ 模糊 IR — Clipboard 无法处理
{
  "type": "event_sheet",
  "description": "让玩家能移动和跳跃"  // 太模糊
}

// ✅ 精确 IR — Clipboard 可确定性渲染
{
  "type": "event_sheet",
  "name": "PlayerMovement",
  "objects": [
    {"name": "Player", "plugin": "Sprite", "behaviors": ["Platform"]}
  ],
  "variables": [
    {"name": "jumpCount", "type": "number", "initial": 0, "scope": "Player"}
  ],
  "events": [
    {
      "conditions": [
        {"plugin": "Platform", "id": "on-landed", "object": "Player"}
      ],
      "actions": [
        {"plugin": "Player", "id": "set-instvar", "params": {"variable": "jumpCount", "value": "0"}}
      ]
    },
    {
      "conditions": [
        {"plugin": "Keyboard", "id": "on-key-pressed", "params": {"key": "38"}},
        {"plugin": "Player", "id": "compare-instance-variable", "params": {"variable": "jumpCount", "comparison": 4, "value": "2"}}
      ],
      "actions": [
        {"plugin": "Platform", "id": "set-vector-y", "object": "Player", "params": {"value": "-600"}},
        {"plugin": "Player", "id": "set-instvar", "params": {"variable": "jumpCount", "value": "jumpCount + 1"}}
      ]
    }
  ]
}
```

Copilot 的 Skill 提示词需要包含 Intent IR 的完整 schema 定义和示例，确保宿主 LLM 输出的 IR 符合 Clipboard 的输入要求。

### RAG 去 LLM 化

当前 RAG 的 `lookup.py` Tier-3 使用 Ollama 做意图分类。整合后改为：
- **Tier-1** (不变)：精确匹配 plugin/behavior 名称
- **Tier-2** (不变)：jieba 分词 + BM25 关键词搜索
- **Tier-3** (改造)：向量语义搜索（embedding model only，不需要 LLM 推理）

embedding model (如 Qwen3-Embedding-0.6B) 不算"LLM"——它是固定的向量映射，确定性输入输出，不做推理。

---

## 6. 数据流示例

### 场景 A：用户在 Claude Code 中说"给我做一个平台跳跃游戏的移动系统"

```
用户 → Copilot
  [1] 意图理解: type=event_sheet, genre=platformer, feature=movement
  [2] Clarification: 需要双跳吗？墙跳？（用户答：要双跳）
  [3] RAG /search: query="Platform behavior jump double-jump"
      → 返回 Platform behavior ACE + 双跳示例事件表
  [4] 路由判断: construct3-mcp 已注册？
      ├─ YES → construct3-mcp 直写
      │   · create_object("Player", behaviors=["Platform"])
      │   · add_instance_variable("Player", "jumpCount", 0)
      │   · create_event_sheet("Movement")
      │   · insert_event(...)  × N
      │   → 告知用户："已在项目中创建 Movement 事件表"
      │
      └─ NO → Clipboard /generate
          · 发送 Intent IR + ACE context
          · 返回剪贴板 JSON
          → 输出 JSON 给用户复制
```

### 场景 B：用户问"Sprite 的 Set animation 怎么用？"

```
用户 → Copilot
  [1] 意图理解: type=question, topic=ace_usage
  [2] RAG /search: query="Sprite Set animation action"
      → 返回 ACE 文档 + 使用示例
  [3] 直接回答用户，无需 Clipboard 或 construct3-mcp
```

---

## 7. Copilot 迁移计划

### Phase 0: 备份
- 当前仓库打 tag `v0-legacy`
- 整个 `.agents/` + `.claude/` + `src/` + `data/` 移入 `.trash/legacy-2026-03-31/`

### Phase 1: Copilot Core 骨架
- 仓库只保留 `.git/`、`LICENSE`、`.gitignore`
- 搭建 FastAPI 服务骨架 (`src/api.py`, `config.py`)
- 实现 LLM 客户端 (`src/llm/client.py` + providers)
- 实现 Session 管理 (`src/orchestrator/session.py`)
- 实现 `/health`, `/chat` 端点
- 核心能力：Construct 3 语义理解（用户自然语言 → 精确 Intent IR）

### Phase 2: 编排管线 + 模块对接
- 实现编排管线 (`src/orchestrator/pipeline.py`)
- 编写 RAG 客户端 (`src/modules/rag_client.py`)
- 编写 Clipboard 客户端 (`src/modules/clipboard_client.py`)
- 实现 construct3-mcp 桥接 (`src/modules/mcp_bridge.py`)
- 实现输出路由 + 降级策略
- 测试各模块在线/离线场景

### Phase 3: CLI 终端前端
- 实现 `frontends/cli/` — readline 交互、输出格式化、剪贴板写入
- 入口: `python -m c3copilot`
- 端到端体验: 用户输入 → Core → RAG + Clipboard → 终端输出

### Phase 4: Claude Code Skill 前端
- 编写 `frontends/skill/CLAUDE.md` — Skill 指令
- 编写 `frontends/skill/SKILL.md` — 触发关键词
- 实现 Core 在线/离线两种模式切换

### Phase 5: 新建 Clipboard 仓库
- 从现有 Copilot 迁移生成逻辑：
  - `src/pipeline/answer.py` → `generator/renderer.py`
  - `src/pipeline/clipboard.py` → `validator/format.py`
  - `references/clipboard-format.md` → `templates/`
  - `scripts/validate_output.py` → `validator/`
  - `scripts/generate_imagedata.py` → `imagedata/`
  - `tests/examples/` → `tests/examples/`
  - `data/checklist.json` → `data/checklist.json`
- 搭建 FastAPI 服务
- 编写 `/generate`、`/validate` 端点
- 对接 RAG 做 ACE 验证

### Phase 6: 端到端测试 + 集成验证
- 全链路测试：用户输入 → CLI → Core → RAG + Clipboard → 输出
- 降级测试：逐个关闭模块验证降级行为
- 回归测试：用现有 examples 验证输出质量不退步
- LLM provider 切换测试：Claude / OpenAI / Ollama

---

## 8. 端口分配

| 服务 | 端口 | 备注 |
|------|------|------|
| Construct3-RAG | 8765 | 已确定 |
| Construct3-Clipboard | 8766 | 新建 |
| Copilot Core | 8767 | 新建，统一编排入口 |
| Qdrant (向量库) | 6333 | RAG 依赖，可选 |
| Ollama (LLM) | 11434 | 开发用，可选 |

---

## 9. 仓库依赖关系

```
construct3-mcp          ← 独立，无依赖
Construct3-RAG          ← 独立，ingest 时引用数据源仓库
Construct3-Clipboard    ← 运行时可调 RAG 做 ACE 验证（可选）
Construct3-Copilot      ← 运行时调用上述三个模块（全部可选）

Construct3-Manual       ← 纯数据，RAG ingest 数据源
Construct-Example-Projects ← 纯数据，RAG ingest 数据源
Construct-Addon-SDK     ← 纯数据，RAG ingest 数据源
```

**关键约束：** 模块间无编译时依赖，全部通过网络接口运行时通信。任何模块可独立开发、测试、部署。
