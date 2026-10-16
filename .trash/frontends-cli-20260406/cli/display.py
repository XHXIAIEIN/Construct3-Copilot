"""Terminal rendering with rich — markdown, JSON, health table, streaming."""
import json
from typing import Optional, List

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

_default_console = Console()

STYLES = {
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "bold cyan",
}


def render_markdown(text: str, console: Console = None) -> None:
    c = console or _default_console
    if not text:
        return
    c.print(Markdown(text))


def render_json(data: dict, console: Console = None) -> None:
    c = console or _default_console
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    c.print(Syntax(formatted, "json", theme="monokai"))


def render_health(status: str, version: str, modules: List[dict], console: Console = None) -> None:
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
    c = console or _default_console
    c.print(token, end="", highlight=False)


def end_stream(console: Console = None) -> None:
    c = console or _default_console
    c.print()


def print_status(text: str, style: str = "info", console: Console = None) -> None:
    c = console or _default_console
    rich_style = STYLES.get(style, style)
    c.print(f"  [{rich_style}]{text}[/{rich_style}]")


def print_welcome(version: str, core_ok: bool, project_name: Optional[str] = None, console: Console = None) -> None:
    c = console or _default_console
    title = Text()
    title.append("\n  ")
    title.append("Construct 3 Copilot CLI", style="bold cyan")
    title.append(f" v{version}")
    c.print(title)
    if core_ok:
        c.print("  Core: [green]✓ connected[/green]")
    else:
        c.print("  Core: [red]✗ unreachable[/red]")
    if project_name:
        c.print(f"  项目: [bold]{project_name}[/bold]")
    c.print("  输入消息开始对话，/help 查看命令\n")
