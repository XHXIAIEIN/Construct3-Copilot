# Phase 3: CLI 终端前端设计规范

> Date: 2026-04-01
> Status: Draft
> Depends on: Phase 1 (Core API), Phase 2 (JSON pipeline)

---

## 1. 目标

构建 Copilot 的首个交互前端 — 一个终端 CLI 对话工具，作为 Copilot Core 的薄客户端。类似 Claude Code 的终端对话体验：用户输入自然语言或粘贴 C3 剪贴板 JSON，CLI 调用 Core API 处理并渲染结果。

**非目标：**
- 不含编排逻辑（全部在 Core）
- 不实现 Web UI 或编辑器插件（Phase 4+）
- 不实现 tab 补全或语法提示（输入是自然语言）

---

## 2. 架构概览

```
用户终端
  │
  ▼
frontends/cli/          ← 本 Phase 交付物
  │  input()  + readline
  │  rich 渲染
  │  pyperclip 剪贴板
  │
  ▼  HTTP (httpx async)
Copilot Core :8767
  ├── POST /chat          (同步)
  ├── POST /chat/stream   (SSE 流式)
  ├── GET  /health
  ├── GET  /session/{id}
  └── DELETE /session/{id}
```

CLI 是纯客户端，不持有任何编排逻辑。所有业务处理由 Core 完成。

---

## 3. 目录结构

```
frontends/
└── cli/
    ├── __init__.py
    ├── __main__.py      # 入口：python -m frontends.cli
    ├── app.py           # CLI 应用主类，持有 client + session 状态
    ├── client.py        # httpx async 客户端，封装 Core API 调用
    ├── repl.py          # REPL 循环：读输入 → 分发命令/消息
    ├── display.py       # rich 渲染：Markdown、JSON 高亮、流式 Live
    ├── clipboard.py     # pyperclip 封装 + 临时文件保存
    └── commands.py      # 斜杠命令注册与分发
```

---

## 4. 模块设计

### 4.1 入口（`__main__.py`）

命令行参数（argparse）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--project PATH` | C3 项目路径，验证含 `.c3proj` 文件 | 无 |
| `--host HOST` | Core 服务地址 | `localhost` |
| `--port PORT` | Core 服务端口 | `8767` |
| `--no-stream` | 禁用流式输出（调试用） | `False` |

启动流程：
1. 解析参数
2. 如有 `--project`，验证目录存在且含 `.c3proj`，不存在则警告（不阻断）
3. 创建 `CopilotApp` 实例
4. `is_available()` 探测 Core，不可用则警告（不阻断）
5. 打印欢迎信息（版本、Core 连接状态、关联项目名）
6. 进入 `run_repl(app)`

### 4.2 应用主类（`app.py`）

```python
class CopilotApp:
    """持有全局状态，贯穿 CLI 生命周期。"""
    client: CopilotClient         # HTTP 客户端
    session_id: Optional[str]     # 当前会话 ID（首次 chat 后由 Core 分配）
    project_path: Optional[str]   # --project 参数
    project_name: Optional[str]   # 从 .c3proj 文件名提取
    stream_enabled: bool          # 是否流式输出
    turn_count: int               # 对话轮数
```

### 4.3 API 客户端（`client.py`）

遵循 Core 现有 `modules/` 客户端模式（`ClipboardClient`、`RAGClient`）：

```python
class CopilotClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """懒初始化，关闭后自动重建。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=120.0,
            )
        return self._client

    async def is_available(self) -> bool     # try health(), except → False
    async def health(self) -> dict           # GET /health
    async def chat(self, message, session_id, context) -> dict
    async def chat_stream(self, message, session_id, context) -> AsyncIterator[str]
    async def get_session(self, session_id) -> dict
    async def delete_session(self, session_id) -> bool
    async def close(self)                    # aclose()
```

**设计对齐：**
- 懒初始化 `@property` — 与 `ClipboardClient` 一致
- `is_available()` 探测 — 与 `ClipboardClient.is_available()` 一致
- 超时 120s — LLM 调用链比 Clipboard 的 60s 更深
- 返回 `dict`（不重定义 Pydantic model）— CLI 是薄客户端，直接消费 Core 的 JSON 响应

**SSE 流式处理：**
- 使用 `httpx` 的 `stream("POST", ...)` 逐行读取
- 普通 token：`data: <token>` → yield token 字符串
- JSON track fallback：`data: {"session_id": ...}` → 检测到完整 JSON 对象，解析为 dict 一次性返回
- 结束标记：`data: [DONE]` → 停止迭代

### 4.4 REPL 循环（`repl.py`）

```python
async def run_repl(app: CopilotApp):
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break                            # Ctrl+D / Ctrl+C 退出
        if not user_input:
            continue
        if user_input.startswith("/"):
            await dispatch_command(app, user_input)
        else:
            await handle_message(app, user_input)
```

- `input()` + `readline`（Unix）/ `pyreadline3`（Windows）提供行编辑和历史
- 不实现多行输入 — C3 剪贴板 JSON 是单行格式
- `Ctrl+C` 在流式输出时中断当前输出（不退出 REPL），在等待输入时退出

**消息处理流程（`handle_message`）：**

1. 构建请求参数（message, session_id, context）
2. 流式模式：调 `client.chat_stream()` → `display.render_stream()` 逐 token 输出
3. 非流式模式：调 `client.chat()` → 一次性渲染
4. 根据响应 `type` 分支处理：
   - `direct_answer` / `clarification` → Markdown 渲染回复
   - `generation` → 自动复制到剪贴板 + 提示"按 V 查看 / S 保存到文件"
   - `error` → 红色高亮
5. 更新 `session_id`（首次由 Core 返回）和 `turn_count`
6. 连接失败 → 友好错误提示，不退出 REPL

### 4.5 斜杠命令（`commands.py`）

```python
COMMANDS = {
    "/help":    cmd_help,       # 显示可用命令列表
    "/health":  cmd_health,     # 调 Core /health，表格渲染模块状态
    "/session": cmd_session,    # 显示 session_id、对话轮数、关联项目
    "/clear":   cmd_clear,      # 删除 session，重置状态
    "/new":     cmd_clear,      # /clear 别名
    "/quit":    cmd_quit,       # 退出 CLI
    "/exit":    cmd_quit,       # /quit 别名
}
```

字典分发，无框架。未知命令提示 `/help`。

### 4.6 渲染（`display.py`）

使用 `rich` 库：

| 函数 | 用途 | rich 组件 |
|------|------|-----------|
| `render_markdown(text)` | 渲染 LLM 回复 | `rich.markdown.Markdown` |
| `render_json(data)` | JSON 语法高亮展示 | `rich.syntax.Syntax` |
| `render_health(modules)` | 模块状态表格 | `rich.table.Table` |
| `render_stream(token_iter)` | 流式逐 token 输出 | `rich.live.Live` |
| `print_status(text, style)` | 状态提示（成功/警告/错误） | `rich.console.Console.print` |
| `print_welcome(version, core_ok, project)` | 欢迎信息 | `Console.print` |

### 4.7 剪贴板（`clipboard.py`）

```python
def copy_json(data: dict) -> bool:
    """将 JSON 写入系统剪贴板。失败时 fallback 到文件保存。"""
    text = json.dumps(data, ensure_ascii=False)
    try:
        pyperclip.copy(text)
        return True
    except pyperclip.PyperclipException:
        path = save_json(data)
        print(f"剪贴板不可用，已保存到 {path}")
        return False

def save_json(data: dict) -> str:
    """保存到 tmp/cli-output-{timestamp}.json，返回路径。"""
    ...
```

---

## 5. 交互体验

### 5.1 启动

```
$ python -m frontends.cli --project D:\MyGame
  Construct 3 Copilot CLI v2.0.0
  Core: http://localhost:8767 ✓
  项目: MyGame (D:\MyGame\MyGame.c3proj)
  
  输入消息开始对话，/help 查看命令
>
```

### 5.2 Q&A 对话（流式）

```
> 怎么给 Sprite 添加平台行为？
  在 Construct 3 中给 Sprite 添加 Platform 行为：
  
  1. 选中 Sprite 对象
  2. 在属性面板点击 "Behaviors"
  3. 点击 "+" 添加 "Platform"
  ...
```

### 5.3 JSON 处理（generation）

```
> {"c3type":"events","items":[...]}  帮我加一个碰撞检测事件
  分析你的事件表 JSON...
  
  已添加碰撞检测事件，包含:
  - 条件: Sprite → Is overlapping → Enemy
  - 动作: Sprite → Destroy
  
  [✓ 已复制到剪贴板]  V 查看JSON | S 保存文件
```

### 5.4 Core 不可用

```
> 帮我写个事件
  ✗ 无法连接 Core (http://localhost:8767)
    请确认 Core 已启动: python -m src.api
>
```

---

## 6. 依赖

| 包 | 用途 | 备注 |
|----|------|------|
| `httpx` | async HTTP 客户端 + SSE | Core 已使用，不是新引入 |
| `rich` | Markdown/JSON 渲染、流式 Live | 新增 |
| `pyperclip` | 跨平台剪贴板写入 | 新增 |
| `pyreadline3` | Windows readline 替代 | 条件依赖，仅 Windows |

**Python ≥ 3.11**，与 Core 一致。

---

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| Core 未启动 | 启动时警告，每次请求时友好提示，不退出 |
| Core 返回 HTTP 错误 | 显示状态码 + 错误信息 |
| SSE 流中断 | 显示已接收的部分内容 + 中断提示 |
| 剪贴板不可用 | fallback 保存到 `tmp/` 文件 |
| `--project` 路径无效 | 启动时警告，仍可正常使用（无项目关联） |
| `Ctrl+C` 在流式输出中 | 中断输出，回到 `>` 提示符 |
| `Ctrl+C` / `Ctrl+D` 在提示符 | 退出 CLI |

---

## 8. 不做的事（YAGNI）

- 历史持久化到文件（内存中的 readline 历史足够）
- 配置文件（环境变量 + 命令行参数足够）
- 插件/扩展系统
- 主题/颜色自定义
- 自动重连/重试（用户手动重试即可）
- 打包为独立可执行文件（后续按需）
