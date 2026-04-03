# Phase 3: CLI Terminal Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a terminal CLI frontend (`frontends/cli/`) that serves as a thin client to Copilot Core :8767, providing REPL-based conversation with streaming output, clipboard integration, and slash commands.

**Architecture:** Pure HTTP client — all orchestration lives in Core. CLI reads user input, sends to Core via httpx, renders responses with rich. Follows existing `ClipboardClient` pattern for async HTTP. Clipboard JSON generation results auto-copied via pyperclip.

**Tech Stack:** Python 3.11+, httpx (async HTTP + SSE), rich (terminal rendering), pyperclip (clipboard), argparse (CLI args), pyreadline3 (Windows readline)

**Core API contract (from `src/schemas/api.py`):**
- `POST /chat` → `ChatRequest{session_id?, message, context}` → `ChatResponse{session_id, type, message, data?, modules_used}`
- `POST /chat/stream` → same request → SSE: `data: <token>\n\n` ... `data: [DONE]\n\n` (JSON track returns full `ChatResponse` as single SSE event)
- `GET /health` → `HealthResponse{status, version, modules[]}`
- `GET /session/{id}` → session dict
- `DELETE /session/{id}` → `{deleted: true}`
- Response types: `direct_answer`, `clarification`, `generation`, `error`
- Generation data: `GenerationData{delivery, clipboard_json?, validation?, input_validation?, metadata?}`

---

## File Structure

```
frontends/
└── cli/
    ├── __init__.py          # Package marker + __version__
    ├── __main__.py          # Entry point: argparse + bootstrap + run_repl
    ├── app.py               # CopilotApp dataclass: holds client + session state
    ├── client.py            # CopilotClient: async httpx wrapper for Core API
    ├── repl.py              # REPL loop: input → dispatch command or message
    ├── display.py           # rich rendering: markdown, JSON, stream, health table
    ├── clipboard.py         # pyperclip wrapper + file fallback
    └── commands.py          # Slash command registry and dispatch

tests/
└── frontends/
    └── cli/
        ├── __init__.py
        ├── test_client.py       # CopilotClient unit tests (httpx mock)
        ├── test_app.py          # CopilotApp unit tests
        ├── test_display.py      # Display rendering tests
        ├── test_clipboard.py    # Clipboard copy/save tests
        ├── test_commands.py     # Slash command dispatch tests
        └── test_repl.py         # REPL integration tests
```

---

## Task 1: Project Scaffolding + Dependencies

**Files:**
- Create: `frontends/__init__.py`
- Create: `frontends/cli/__init__.py`
- Create: `tests/frontends/__init__.py`
- Create: `tests/frontends/cli/__init__.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Create package directories**

```
frontends/__init__.py        → empty
frontends/cli/__init__.py    → __version__ = "0.1.0"
tests/frontends/__init__.py  → empty
tests/frontends/cli/__init__.py → empty
```

- [ ] **Step 2: Add CLI dependencies to requirements.txt**

Append to `requirements.txt`:

```
# CLI Frontend (Phase 3)
rich>=13.0.0
pyperclip>=1.9.0
pyreadline3>=3.5.0; sys_platform == "win32"
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 4: Verify import works**

Run: `python -c "import frontends.cli; print(frontends.cli.__version__)"`
Expected: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add frontends/ tests/frontends/ requirements.txt
git commit -m "feat(phase3): scaffold CLI frontend package and dependencies"
```

---

## Task 2: CopilotClient — HTTP Client

**Files:**
- Create: `frontends/cli/client.py`
- Create: `tests/frontends/cli/test_client.py`

- [ ] **Step 1: Write failing tests for CopilotClient**

```python
# tests/frontends/cli/test_client.py
"""Tests for CopilotClient — async HTTP wrapper for Core API."""
import json
import pytest
import httpx

from frontends.cli.client import CopilotClient


@pytest.fixture
def client():
    return CopilotClient(base_url="http://localhost:8767")


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_success(self, client):
        """health() returns parsed JSON from GET /health."""
        mock_response = {"status": "ok", "version": "2.0.0", "modules": []}

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/health"
            return httpx.Response(200, json=mock_response)

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.health()
        assert result == mock_response
        await client.close()

    @pytest.mark.asyncio
    async def test_is_available_true(self, client):
        """is_available() returns True when health succeeds."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, json={"status": "ok"})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.is_available() is True
        await client.close()

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self, client):
        """is_available() returns False when health fails."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(500, text="Internal Server Error")

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.is_available() is False
        await client.close()


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self, client):
        """chat() POSTs correct JSON to /chat and returns response dict."""
        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/chat"
            body = json.loads(request.content)
            assert body["message"] == "hello"
            assert body["session_id"] == "s1"
            assert body["context"]["has_local_project"] is True
            return httpx.Response(200, json={
                "session_id": "s1",
                "type": "direct_answer",
                "message": "Hi there!",
                "modules_used": [],
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.chat(
            message="hello",
            session_id="s1",
            context={"has_local_project": True},
        )
        assert result["type"] == "direct_answer"
        assert result["message"] == "Hi there!"
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_without_session_id(self, client):
        """chat() works without session_id (first turn)."""
        async def mock_handler(request: httpx.Request):
            body = json.loads(request.content)
            assert body["session_id"] is None
            return httpx.Response(200, json={
                "session_id": "new-id",
                "type": "direct_answer",
                "message": "Hello!",
                "modules_used": [],
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.chat(message="hi", session_id=None)
        assert result["session_id"] == "new-id"
        await client.close()


class TestChatStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, client):
        """chat_stream() yields individual tokens from SSE stream."""
        sse_body = "data: Hello\n\ndata:  world\n\ndata: [DONE]\n\n"

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/chat/stream"
            return httpx.Response(200, text=sse_body, headers={
                "content-type": "text/event-stream",
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        tokens = []
        async for chunk in client.chat_stream(message="test"):
            tokens.append(chunk)
        assert tokens == ["Hello", " world"]
        await client.close()

    @pytest.mark.asyncio
    async def test_stream_json_fallback(self, client):
        """chat_stream() yields full JSON dict for JSON track responses."""
        response_dict = {
            "session_id": "s1", "type": "generation",
            "message": "Done", "data": {"delivery": "clipboard"},
            "modules_used": ["llm"],
        }
        sse_body = f"data: {json.dumps(response_dict)}\n\ndata: [DONE]\n\n"

        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, text=sse_body, headers={
                "content-type": "text/event-stream",
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        results = []
        async for chunk in client.chat_stream(message="test"):
            results.append(chunk)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["type"] == "generation"
        await client.close()


class TestSession:
    @pytest.mark.asyncio
    async def test_get_session(self, client):
        """get_session() fetches session by ID."""
        session_data = {"session_id": "s1", "messages": [], "turn_count": 0}

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/session/s1"
            return httpx.Response(200, json=session_data)

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.get_session("s1")
        assert result["session_id"] == "s1"
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        """delete_session() returns True on success."""
        async def mock_handler(request: httpx.Request):
            assert request.method == "DELETE"
            return httpx.Response(200, json={"deleted": True})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.delete_session("s1") is True
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, client):
        """delete_session() returns False on 404."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(404, json={"detail": "Session not found"})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.delete_session("nonexistent") is False
        await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_client.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'frontends.cli.client'`

- [ ] **Step 3: Implement CopilotClient**

```python
# frontends/cli/client.py
"""Async HTTP client for Copilot Core API.

Follows the same lazy-init pattern as ClipboardClient in src/modules/.
"""
import json
from typing import AsyncIterator, Optional

import httpx


class CopilotClient:
    """HTTP wrapper for Copilot Core endpoints."""

    def __init__(self, base_url: str = "http://localhost:8767"):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client. Recreates if closed."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=120.0,
            )
        return self._client

    async def health(self) -> dict:
        """GET /health — returns parsed JSON."""
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def is_available(self) -> bool:
        """Check if Core is reachable."""
        try:
            await self.health()
            return True
        except Exception:
            return False

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """POST /chat — synchronous chat, returns full response dict."""
        payload = {
            "message": message,
            "session_id": session_id,
            "context": context or {},
        }
        resp = await self.client.post("/chat", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncIterator:
        """POST /chat/stream — yields str tokens or dict (JSON track fallback).

        SSE format from Core:
        - Regular token: "data: <text>\n\n" → yield str
        - JSON fallback:  "data: {\"session_id\": ...}\n\n" → yield dict
        - End marker:     "data: [DONE]\n\n" → stop
        """
        payload = {
            "message": message,
            "session_id": session_id,
            "context": context or {},
        }
        resp = await self.client.post("/chat/stream", json=payload)
        resp.raise_for_status()
        for line in resp.text.split("\n"):
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]  # strip "data: "
            if data == "[DONE]":
                return
            # Try JSON parse — if it looks like a full ChatResponse dict
            if data.startswith("{"):
                try:
                    parsed = json.loads(data)
                    if "session_id" in parsed:
                        yield parsed
                        continue
                except json.JSONDecodeError:
                    pass
            yield data

    async def get_session(self, session_id: str) -> dict:
        """GET /session/{id} — returns session state dict."""
        resp = await self.client.get(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_session(self, session_id: str) -> bool:
        """DELETE /session/{id} — returns True if deleted, False if not found."""
        resp = await self.client.delete(f"/session/{session_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    async def close(self):
        """Close the underlying httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/client.py tests/frontends/cli/test_client.py
git commit -m "feat(phase3): add CopilotClient with async HTTP + SSE streaming"
```

---

## Task 3: CopilotApp — Application State

**Files:**
- Create: `frontends/cli/app.py`
- Create: `tests/frontends/cli/test_app.py`

- [ ] **Step 1: Write failing tests for CopilotApp**

```python
# tests/frontends/cli/test_app.py
"""Tests for CopilotApp — application state container."""
import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from frontends.cli.app import CopilotApp


class TestInit:
    def test_default_state(self):
        """CopilotApp initializes with sensible defaults."""
        app = CopilotApp(host="localhost", port=8767)
        assert app.session_id is None
        assert app.project_path is None
        assert app.project_name is None
        assert app.stream_enabled is True
        assert app.turn_count == 0
        assert app.client is not None

    def test_with_project(self, tmp_path):
        """CopilotApp extracts project name from .c3proj file."""
        proj_file = tmp_path / "MyGame.c3proj"
        proj_file.write_text("{}")
        app = CopilotApp(host="localhost", port=8767, project_path=str(tmp_path))
        assert app.project_path == str(tmp_path)
        assert app.project_name == "MyGame"

    def test_with_invalid_project_path(self):
        """CopilotApp sets project_name=None for invalid path."""
        app = CopilotApp(host="localhost", port=8767, project_path="/nonexistent")
        assert app.project_path == "/nonexistent"
        assert app.project_name is None

    def test_no_stream(self):
        """stream_enabled=False disables streaming."""
        app = CopilotApp(host="localhost", port=8767, stream_enabled=False)
        assert app.stream_enabled is False


class TestContext:
    def test_build_context_with_project(self, tmp_path):
        """build_context() returns has_local_project=True when project set."""
        proj_file = tmp_path / "MyGame.c3proj"
        proj_file.write_text("{}")
        app = CopilotApp(host="localhost", port=8767, project_path=str(tmp_path))
        ctx = app.build_context()
        assert ctx["has_local_project"] is True
        assert ctx["project_path"] == str(tmp_path)

    def test_build_context_without_project(self):
        """build_context() returns has_local_project=False when no project."""
        app = CopilotApp(host="localhost", port=8767)
        ctx = app.build_context()
        assert ctx["has_local_project"] is False


class TestUpdateSession:
    def test_update_from_response(self):
        """update_from_response() extracts session_id and increments turn count."""
        app = CopilotApp(host="localhost", port=8767)
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        assert app.session_id == "abc123"
        assert app.turn_count == 1

    def test_preserves_existing_session_id(self):
        """update_from_response() keeps session_id consistent."""
        app = CopilotApp(host="localhost", port=8767)
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        assert app.turn_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement CopilotApp**

```python
# frontends/cli/app.py
"""CLI application state — holds client, session, and project info."""
from pathlib import Path
from typing import Optional

from frontends.cli.client import CopilotClient


class CopilotApp:
    """Global state container for the CLI lifecycle."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8767,
        project_path: Optional[str] = None,
        stream_enabled: bool = True,
    ):
        self.client = CopilotClient(base_url=f"http://{host}:{port}")
        self.session_id: Optional[str] = None
        self.project_path = project_path
        self.project_name = self._detect_project_name(project_path)
        self.stream_enabled = stream_enabled
        self.turn_count: int = 0

    @staticmethod
    def _detect_project_name(project_path: Optional[str]) -> Optional[str]:
        """Extract project name from first .c3proj file in directory."""
        if not project_path:
            return None
        p = Path(project_path)
        if not p.is_dir():
            return None
        for f in p.glob("*.c3proj"):
            return f.stem
        return None

    def build_context(self) -> dict:
        """Build ChatContext dict for API requests."""
        if self.project_path and self.project_name:
            return {"has_local_project": True, "project_path": self.project_path}
        return {"has_local_project": False}

    def update_from_response(self, response: dict) -> None:
        """Extract session_id from response and increment turn count."""
        if sid := response.get("session_id"):
            self.session_id = sid
        self.turn_count += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_app.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/app.py tests/frontends/cli/test_app.py
git commit -m "feat(phase3): add CopilotApp application state container"
```

---

## Task 4: Display Module — Rich Rendering

**Files:**
- Create: `frontends/cli/display.py`
- Create: `tests/frontends/cli/test_display.py`

- [ ] **Step 1: Write failing tests for display functions**

```python
# tests/frontends/cli/test_display.py
"""Tests for display module — rich rendering functions."""
import json
import pytest
from io import StringIO
from rich.console import Console

from frontends.cli.display import (
    render_markdown,
    render_json,
    render_health,
    print_status,
    print_welcome,
)


@pytest.fixture
def capture_console():
    """Create a Console that captures output to a string."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    return console, buf


class TestRenderMarkdown:
    def test_renders_markdown_text(self, capture_console):
        console, buf = capture_console
        render_markdown("**bold** and *italic*", console=console)
        output = buf.getvalue()
        assert "bold" in output

    def test_handles_empty_string(self, capture_console):
        console, buf = capture_console
        render_markdown("", console=console)
        # Should not raise


class TestRenderJson:
    def test_renders_json_with_syntax_highlighting(self, capture_console):
        console, buf = capture_console
        render_json({"key": "value"}, console=console)
        output = buf.getvalue()
        assert "key" in output
        assert "value" in output


class TestRenderHealth:
    def test_renders_health_table(self, capture_console):
        console, buf = capture_console
        modules = [
            {"name": "llm", "available": True, "detail": "claude"},
            {"name": "rag", "available": False, "detail": "unreachable"},
        ]
        render_health(status="degraded", version="2.0.0", modules=modules, console=console)
        output = buf.getvalue()
        assert "llm" in output
        assert "rag" in output


class TestPrintStatus:
    def test_success_style(self, capture_console):
        console, buf = capture_console
        print_status("Done!", style="success", console=console)
        output = buf.getvalue()
        assert "Done!" in output

    def test_error_style(self, capture_console):
        console, buf = capture_console
        print_status("Failed", style="error", console=console)
        output = buf.getvalue()
        assert "Failed" in output


class TestPrintWelcome:
    def test_welcome_with_project(self, capture_console):
        console, buf = capture_console
        print_welcome(version="0.1.0", core_ok=True, project_name="MyGame", console=console)
        output = buf.getvalue()
        assert "MyGame" in output
        assert "0.1.0" in output

    def test_welcome_without_project(self, capture_console):
        console, buf = capture_console
        print_welcome(version="0.1.0", core_ok=False, project_name=None, console=console)
        output = buf.getvalue()
        assert "0.1.0" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_display.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement display module**

```python
# frontends/cli/display.py
"""Terminal rendering with rich — markdown, JSON, health table, streaming."""
import json
from typing import Optional, List

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

# Module-level default console (overridable for testing)
_default_console = Console()

STYLES = {
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "bold cyan",
}


def render_markdown(text: str, console: Console = None) -> None:
    """Render markdown text to terminal."""
    c = console or _default_console
    if not text:
        return
    c.print(Markdown(text))


def render_json(data: dict, console: Console = None) -> None:
    """Render JSON with syntax highlighting."""
    c = console or _default_console
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    c.print(Syntax(formatted, "json", theme="monokai"))


def render_health(
    status: str,
    version: str,
    modules: List[dict],
    console: Console = None,
) -> None:
    """Render Core health as a table."""
    c = console or _default_console
    status_style = {"ok": "green", "degraded": "yellow", "error": "red"}.get(status, "white")
    c.print(f"\nCopilot Core v{version}  [{status_style}]{status}[/{status_style}]\n")

    table = Table(show_header=True)
    table.add_column("Module", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")
    for m in modules:
        status_icon = "[green]✓[/green]" if m["available"] else "[red]✗[/red]"
        table.add_row(m["name"], status_icon, m.get("detail", ""))
    c.print(table)


def render_stream_token(token: str, console: Console = None) -> None:
    """Print a single streaming token without newline."""
    c = console or _default_console
    c.print(token, end="", highlight=False)


def end_stream(console: Console = None) -> None:
    """Print newline after streaming completes."""
    c = console or _default_console
    c.print()


def print_status(text: str, style: str = "info", console: Console = None) -> None:
    """Print a styled status message."""
    c = console or _default_console
    rich_style = STYLES.get(style, style)
    c.print(f"  [{rich_style}]{text}[/{rich_style}]")


def print_welcome(
    version: str,
    core_ok: bool,
    project_name: Optional[str] = None,
    console: Console = None,
) -> None:
    """Print welcome banner on CLI startup."""
    c = console or _default_console
    c.print(f"\n  [bold cyan]Construct 3 Copilot CLI[/bold cyan] v{version}")
    if core_ok:
        c.print("  Core: [green]✓ connected[/green]")
    else:
        c.print("  Core: [red]✗ unreachable[/red]")
    if project_name:
        c.print(f"  项目: [bold]{project_name}[/bold]")
    c.print("  输入消息开始对话，/help 查看命令\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_display.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/display.py tests/frontends/cli/test_display.py
git commit -m "feat(phase3): add rich-based display rendering module"
```

---

## Task 5: Clipboard Module

**Files:**
- Create: `frontends/cli/clipboard.py`
- Create: `tests/frontends/cli/test_clipboard.py`

- [ ] **Step 1: Write failing tests for clipboard functions**

```python
# tests/frontends/cli/test_clipboard.py
"""Tests for clipboard module — copy + file fallback."""
import json
import pytest
from unittest.mock import patch
from pathlib import Path

from frontends.cli.clipboard import copy_json, save_json


class TestSaveJson:
    def test_save_creates_file(self, tmp_path):
        """save_json() writes JSON to tmp/ directory."""
        data = {"c3type": "events", "items": []}
        path = save_json(data, output_dir=tmp_path)
        assert Path(path).exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_filename_pattern(self, tmp_path):
        """save_json() filename starts with cli-output-."""
        data = {"key": "value"}
        path = save_json(data, output_dir=tmp_path)
        assert "cli-output-" in Path(path).name
        assert path.endswith(".json")


class TestCopyJson:
    @patch("frontends.cli.clipboard.pyperclip")
    def test_copy_success(self, mock_pyperclip):
        """copy_json() calls pyperclip.copy and returns True."""
        data = {"c3type": "events"}
        result = copy_json(data)
        assert result is True
        mock_pyperclip.copy.assert_called_once()
        copied_text = mock_pyperclip.copy.call_args[0][0]
        assert json.loads(copied_text) == data

    @patch("frontends.cli.clipboard.pyperclip")
    def test_copy_fallback_on_error(self, mock_pyperclip, tmp_path):
        """copy_json() falls back to save_json when pyperclip fails."""
        mock_pyperclip.copy.side_effect = Exception("No clipboard")
        data = {"c3type": "events"}
        result = copy_json(data, fallback_dir=tmp_path)
        assert result is False
        # Should have saved a file
        files = list(tmp_path.glob("cli-output-*.json"))
        assert len(files) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_clipboard.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement clipboard module**

```python
# frontends/cli/clipboard.py
"""Clipboard integration — copy JSON to system clipboard with file fallback."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyperclip


def save_json(data: dict, output_dir: Optional[Path] = None) -> str:
    """Save JSON to a timestamped file. Returns the file path."""
    if output_dir is None:
        output_dir = Path("tmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"cli-output-{timestamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def copy_json(data: dict, fallback_dir: Optional[Path] = None) -> bool:
    """Copy JSON to system clipboard. Falls back to file save on failure.

    Returns True if copied to clipboard, False if fell back to file.
    """
    text = json.dumps(data, ensure_ascii=False)
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        path = save_json(data, output_dir=fallback_dir)
        print(f"  剪贴板不可用，已保存到 {path}")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_clipboard.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/clipboard.py tests/frontends/cli/test_clipboard.py
git commit -m "feat(phase3): add clipboard copy with file fallback"
```

---

## Task 6: Slash Commands

**Files:**
- Create: `frontends/cli/commands.py`
- Create: `tests/frontends/cli/test_commands.py`

- [ ] **Step 1: Write failing tests for commands**

```python
# tests/frontends/cli/test_commands.py
"""Tests for slash command dispatch."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO
from rich.console import Console

from frontends.cli.commands import dispatch_command, COMMANDS
from frontends.cli.app import CopilotApp


@pytest.fixture
def app():
    app = CopilotApp(host="localhost", port=8767)
    return app


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestDispatch:
    @pytest.mark.asyncio
    async def test_help_command(self, app, console):
        con, buf = console
        await dispatch_command(app, "/help", console=con)
        output = buf.getvalue()
        assert "/help" in output
        assert "/health" in output

    @pytest.mark.asyncio
    async def test_unknown_command(self, app, console):
        con, buf = console
        await dispatch_command(app, "/foobar", console=con)
        output = buf.getvalue()
        assert "/help" in output  # should suggest /help

    @pytest.mark.asyncio
    async def test_health_command(self, app, console):
        con, buf = console
        app.client.health = AsyncMock(return_value={
            "status": "ok",
            "version": "2.0.0",
            "modules": [{"name": "llm", "available": True, "detail": "claude"}],
        })
        await dispatch_command(app, "/health", console=con)
        output = buf.getvalue()
        assert "llm" in output

    @pytest.mark.asyncio
    async def test_health_command_core_down(self, app, console):
        con, buf = console
        app.client.health = AsyncMock(side_effect=Exception("Connection refused"))
        await dispatch_command(app, "/health", console=con)
        output = buf.getvalue()
        # Should show error, not crash
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_session_command(self, app, console):
        con, buf = console
        app.session_id = "test-123"
        app.turn_count = 5
        app.project_name = "MyGame"
        await dispatch_command(app, "/session", console=con)
        output = buf.getvalue()
        assert "test-123" in output

    @pytest.mark.asyncio
    async def test_clear_resets_session(self, app, console):
        con, buf = console
        app.session_id = "old-session"
        app.turn_count = 3
        app.client.delete_session = AsyncMock(return_value=True)
        await dispatch_command(app, "/clear", console=con)
        assert app.session_id is None
        assert app.turn_count == 0

    @pytest.mark.asyncio
    async def test_quit_raises_systemexit(self, app, console):
        con, buf = console
        with pytest.raises(SystemExit):
            await dispatch_command(app, "/quit", console=con)

    @pytest.mark.asyncio
    async def test_exit_alias(self, app, console):
        con, buf = console
        with pytest.raises(SystemExit):
            await dispatch_command(app, "/exit", console=con)


class TestCommandRegistry:
    def test_all_commands_registered(self):
        expected = {"/help", "/health", "/session", "/clear", "/new", "/quit", "/exit"}
        assert expected == set(COMMANDS.keys())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement commands module**

```python
# frontends/cli/commands.py
"""Slash command registry and dispatch."""
from typing import TYPE_CHECKING

from rich.console import Console

from frontends.cli import display

if TYPE_CHECKING:
    from frontends.cli.app import CopilotApp

# Module-level default console
_default_console = Console()


async def cmd_help(app: "CopilotApp", console: Console) -> None:
    """Show available commands."""
    lines = [
        "[bold]可用命令:[/bold]",
        "  /help     显示此帮助",
        "  /health   Core 服务状态",
        "  /session  当前会话信息",
        "  /clear    清除会话（/new 同义）",
        "  /quit     退出（/exit 同义）",
    ]
    console.print("\n".join(lines))


async def cmd_health(app: "CopilotApp", console: Console) -> None:
    """Show Core health status."""
    try:
        data = await app.client.health()
        display.render_health(
            status=data["status"],
            version=data["version"],
            modules=data.get("modules", []),
            console=console,
        )
    except Exception as e:
        display.print_status(f"无法连接 Core: {e}", style="error", console=console)


async def cmd_session(app: "CopilotApp", console: Console) -> None:
    """Show current session info."""
    lines = []
    lines.append(f"  Session: {app.session_id or '(未开始)'}")
    lines.append(f"  对话轮数: {app.turn_count}")
    if app.project_name:
        lines.append(f"  项目: {app.project_name}")
    console.print("\n".join(lines))


async def cmd_clear(app: "CopilotApp", console: Console) -> None:
    """Clear session and reset state."""
    if app.session_id:
        try:
            await app.client.delete_session(app.session_id)
        except Exception:
            pass
    app.session_id = None
    app.turn_count = 0
    display.print_status("会话已清除", style="success", console=console)


async def cmd_quit(app: "CopilotApp", console: Console) -> None:
    """Exit the CLI."""
    await app.client.close()
    raise SystemExit(0)


COMMANDS = {
    "/help": cmd_help,
    "/health": cmd_health,
    "/session": cmd_session,
    "/clear": cmd_clear,
    "/new": cmd_clear,
    "/quit": cmd_quit,
    "/exit": cmd_quit,
}


async def dispatch_command(
    app: "CopilotApp",
    user_input: str,
    console: Console = None,
) -> None:
    """Parse and dispatch a slash command."""
    c = console or _default_console
    cmd_name = user_input.strip().split()[0].lower()
    handler = COMMANDS.get(cmd_name)
    if handler:
        await handler(app, c)
    else:
        display.print_status(f"未知命令: {cmd_name}，输入 /help 查看可用命令", style="warning", console=c)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_commands.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/commands.py tests/frontends/cli/test_commands.py
git commit -m "feat(phase3): add slash command registry and dispatch"
```

---

## Task 7: REPL Loop + Message Handling

**Files:**
- Create: `frontends/cli/repl.py`
- Create: `tests/frontends/cli/test_repl.py`

- [ ] **Step 1: Write failing tests for REPL message handling**

```python
# tests/frontends/cli/test_repl.py
"""Tests for REPL message handling logic."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import StringIO
from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.repl import handle_message


@pytest.fixture
def app():
    a = CopilotApp(host="localhost", port=8767)
    return a


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestHandleMessageNonStreaming:
    @pytest.mark.asyncio
    async def test_direct_answer(self, app, console):
        """direct_answer renders markdown response."""
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "direct_answer",
            "message": "This is the **answer**.",
            "modules_used": ["rag"],
        })
        await handle_message(app, "how do I use Platform?", console=con)
        output = buf.getvalue()
        assert "answer" in output
        assert app.session_id == "s1"
        assert app.turn_count == 1

    @pytest.mark.asyncio
    async def test_generation_copies_to_clipboard(self, app, console):
        """generation type auto-copies clipboard_json."""
        con, buf = console
        app.stream_enabled = False
        clipboard_data = {"c3type": "events", "items": []}
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "generation",
            "message": "Here's your event sheet.",
            "data": {
                "delivery": "clipboard",
                "clipboard_json": clipboard_data,
            },
            "modules_used": ["llm"],
        })
        with patch("frontends.cli.repl.copy_json", return_value=True) as mock_copy:
            await handle_message(app, '{"c3type":"events"} add collision', console=con)
            mock_copy.assert_called_once_with(clipboard_data)

    @pytest.mark.asyncio
    async def test_error_response(self, app, console):
        """error type renders error message."""
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "error",
            "message": "LLM error: timeout",
            "modules_used": [],
        })
        await handle_message(app, "do something", console=con)
        output = buf.getvalue()
        assert "error" in output.lower() or "LLM" in output

    @pytest.mark.asyncio
    async def test_connection_error(self, app, console):
        """Connection failure shows friendly error, doesn't crash."""
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(side_effect=Exception("Connection refused"))
        await handle_message(app, "hello", console=con)
        output = buf.getvalue()
        assert len(output) > 0  # showed an error
        # REPL should not have crashed


class TestHandleMessageStreaming:
    @pytest.mark.asyncio
    async def test_stream_tokens(self, app, console):
        """Streaming mode renders tokens as they arrive."""
        con, buf = console
        app.stream_enabled = True

        async def fake_stream(*args, **kwargs):
            for token in ["Hello", " ", "world"]:
                yield token

        app.client.chat_stream = fake_stream
        await handle_message(app, "hi", console=con)
        output = buf.getvalue()
        assert "Hello" in output
        assert "world" in output

    @pytest.mark.asyncio
    async def test_stream_json_fallback(self, app, console):
        """Streaming with JSON track returns full response dict."""
        con, buf = console
        app.stream_enabled = True
        response_dict = {
            "session_id": "s1",
            "type": "generation",
            "message": "Generated.",
            "data": {"delivery": "clipboard", "clipboard_json": {"c3type": "events"}},
            "modules_used": ["llm"],
        }

        async def fake_stream(*args, **kwargs):
            yield response_dict

        app.client.chat_stream = fake_stream
        with patch("frontends.cli.repl.copy_json", return_value=True):
            await handle_message(app, '{"c3type":"events"}', console=con)
        assert app.session_id == "s1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/frontends/cli/test_repl.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement REPL module**

```python
# frontends/cli/repl.py
"""REPL loop — read input, dispatch commands or send messages."""
import asyncio
import sys
from typing import Optional

from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.clipboard import copy_json
from frontends.cli import display
from frontends.cli.commands import dispatch_command

_default_console = Console()


async def handle_message(
    app: CopilotApp,
    user_input: str,
    console: Console = None,
) -> None:
    """Send a message to Core and render the response."""
    c = console or _default_console
    context = app.build_context()

    if app.stream_enabled:
        await _handle_streaming(app, user_input, context, c)
    else:
        await _handle_sync(app, user_input, context, c)


async def _handle_sync(
    app: CopilotApp,
    message: str,
    context: dict,
    console: Console,
) -> None:
    """Non-streaming: call /chat, render full response."""
    try:
        response = await app.client.chat(
            message=message,
            session_id=app.session_id,
            context=context,
        )
    except Exception as e:
        display.print_status(
            f"无法连接 Core ({app.client.base_url})\n  请确认 Core 已启动: python -m src.api",
            style="error",
            console=console,
        )
        return

    app.update_from_response(response)
    _render_response(response, console)


async def _handle_streaming(
    app: CopilotApp,
    message: str,
    context: dict,
    console: Console,
) -> None:
    """Streaming: call /chat/stream, render tokens as they arrive."""
    try:
        stream = app.client.chat_stream(
            message=message,
            session_id=app.session_id,
            context=context,
        )
    except Exception as e:
        display.print_status(
            f"无法连接 Core ({app.client.base_url})",
            style="error",
            console=console,
        )
        return

    try:
        async for chunk in stream:
            if isinstance(chunk, dict):
                # JSON track fallback — full response dict
                app.update_from_response(chunk)
                _render_response(chunk, console)
                return
            else:
                display.render_stream_token(chunk, console=console)
        display.end_stream(console=console)
        # Streaming Q&A doesn't return session_id in tokens;
        # update turn count only
        app.turn_count += 1
    except KeyboardInterrupt:
        display.end_stream(console=console)
        display.print_status("输出已中断", style="warning", console=console)
    except Exception as e:
        display.end_stream(console=console)
        display.print_status(f"流式传输中断: {e}", style="error", console=console)


def _render_response(response: dict, console: Console) -> None:
    """Render a full ChatResponse dict based on type."""
    resp_type = response.get("type", "direct_answer")
    message = response.get("message", "")

    if resp_type == "error":
        display.print_status(message, style="error", console=console)
    elif resp_type == "generation":
        display.render_markdown(message, console=console)
        # Auto-copy clipboard JSON
        data = response.get("data") or {}
        clipboard_json = data.get("clipboard_json")
        if clipboard_json:
            copied = copy_json(clipboard_json)
            if copied:
                display.print_status("已复制到剪贴板", style="success", console=console)
    else:
        # direct_answer, clarification
        display.render_markdown(message, console=console)


async def run_repl(app: CopilotApp, console: Console = None) -> None:
    """Main REPL loop — blocks until user exits."""
    c = console or _default_console

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("> "),
            )
        except (EOFError, KeyboardInterrupt):
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            try:
                await dispatch_command(app, user_input, console=c)
            except SystemExit:
                break
        else:
            await handle_message(app, user_input, console=c)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/frontends/cli/test_repl.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontends/cli/repl.py tests/frontends/cli/test_repl.py
git commit -m "feat(phase3): add REPL loop with streaming and sync message handling"
```

---

## Task 8: Entry Point (`__main__.py`)

**Files:**
- Create: `frontends/cli/__main__.py`

- [ ] **Step 1: Implement __main__.py**

```python
# frontends/cli/__main__.py
"""Entry point: python -m frontends.cli

Parses CLI args, bootstraps CopilotApp, and starts the REPL.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from frontends.cli import __version__
from frontends.cli.app import CopilotApp
from frontends.cli.display import print_welcome, print_status
from frontends.cli.repl import run_repl

# Windows readline support
if sys.platform == "win32":
    try:
        import pyreadline3  # noqa: F401 — registers itself as readline
    except ImportError:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="copilot-cli",
        description="Construct 3 Copilot CLI — terminal frontend for Copilot Core",
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Path to C3 project directory (must contain .c3proj file)",
    )
    parser.add_argument("--host", type=str, default="localhost", help="Core host")
    parser.add_argument("--port", type=int, default=8767, help="Core port")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Validate project path
    if args.project:
        p = Path(args.project)
        if not p.is_dir():
            print_status(f"警告: 项目路径不存在: {args.project}", style="warning")
        elif not list(p.glob("*.c3proj")):
            print_status(f"警告: 未找到 .c3proj 文件: {args.project}", style="warning")

    app = CopilotApp(
        host=args.host,
        port=args.port,
        project_path=args.project,
        stream_enabled=not args.no_stream,
    )

    # Probe Core
    core_ok = await app.client.is_available()

    print_welcome(
        version=__version__,
        core_ok=core_ok,
        project_name=app.project_name,
    )

    await run_repl(app)
    await app.client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify entry point works (dry run)**

Run: `python -m frontends.cli --help`
Expected:
```
usage: copilot-cli [-h] [--project PROJECT] [--host HOST] [--port PORT] [--no-stream]
```

- [ ] **Step 3: Commit**

```bash
git add frontends/cli/__main__.py
git commit -m "feat(phase3): add CLI entry point with argparse bootstrap"
```

---

## Task 9: Integration Smoke Test

**Files:**
- Create: `tests/frontends/cli/test_integration.py`

- [ ] **Step 1: Write integration test (mocked Core)**

```python
# tests/frontends/cli/test_integration.py
"""Integration smoke test — full CLI flow with mocked Core."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from io import StringIO
from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.repl import handle_message
from frontends.cli.commands import dispatch_command


@pytest.fixture
def app():
    return CopilotApp(host="localhost", port=8767)


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestFullFlow:
    @pytest.mark.asyncio
    async def test_qa_then_clear_then_qa(self, app, console):
        """Simulate: ask question → /clear → ask again."""
        con, buf = console
        app.stream_enabled = False

        # First question
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "direct_answer",
            "message": "Platform behavior docs...",
            "modules_used": ["rag"],
        })
        await handle_message(app, "how to add Platform?", console=con)
        assert app.session_id == "s1"
        assert app.turn_count == 1

        # Clear
        app.client.delete_session = AsyncMock(return_value=True)
        await dispatch_command(app, "/clear", console=con)
        assert app.session_id is None
        assert app.turn_count == 0

        # Second question (new session)
        app.client.chat = AsyncMock(return_value={
            "session_id": "s2",
            "type": "direct_answer",
            "message": "Solid behavior docs...",
            "modules_used": [],
        })
        await handle_message(app, "how to add Solid?", console=con)
        assert app.session_id == "s2"
        assert app.turn_count == 1

    @pytest.mark.asyncio
    async def test_json_generation_flow(self, app, console):
        """Simulate: paste JSON → get generation → clipboard copy."""
        con, buf = console
        app.stream_enabled = False
        clipboard_json = {"c3type": "events", "items": [{"type": "event"}]}

        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "generation",
            "message": "Added collision event.",
            "data": {
                "delivery": "clipboard",
                "clipboard_json": clipboard_json,
            },
            "modules_used": ["llm", "rag"],
        })

        with patch("frontends.cli.repl.copy_json", return_value=True) as mock_copy:
            await handle_message(app, '{"c3type":"events"} add collision', console=con)
            mock_copy.assert_called_once_with(clipboard_json)
        
        output = buf.getvalue()
        assert "collision" in output.lower() or "已复制" in output
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/frontends/cli/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/frontends/cli/test_integration.py
git commit -m "test(phase3): add integration smoke tests for CLI frontend"
```

---

## Task 10: Final Polish + Full Test Run

- [ ] **Step 1: Run full test suite to confirm nothing is broken**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (both existing Core tests and new CLI tests)

- [ ] **Step 2: Verify CLI launches**

Run: `python -m frontends.cli --no-stream`
Expected: Shows welcome banner, Core status (✗ if not running), waits for input. `Ctrl+C` exits.

- [ ] **Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "feat(phase3): complete CLI terminal frontend"
```
