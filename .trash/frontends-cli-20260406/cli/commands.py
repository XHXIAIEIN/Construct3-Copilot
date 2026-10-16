"""Slash command registry and dispatch."""
from typing import TYPE_CHECKING

from rich.console import Console

from frontends.cli import display

if TYPE_CHECKING:
    from frontends.cli.app import CopilotApp

_default_console = Console()


async def cmd_help(app: "CopilotApp", console: Console) -> None:
    lines = [
        "[bold]可用命令:[/bold]",
        "  /help     显示此帮助",
        "  /health   Core 服务状态",
        "  /session  当前会话信息",
        "  /clear    清除会话（/new 同义）",
        "  /quit     退出（/exit 同义）",
    ]
    console.print("\n".join(lines), highlight=False)


async def cmd_health(app: "CopilotApp", console: Console) -> None:
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
    lines = []
    lines.append(f"  Session: {app.session_id or '(未开始)'}")
    lines.append(f"  对话轮数: {app.turn_count}")
    if app.project_name:
        lines.append(f"  项目: {app.project_name}")
    console.print("\n".join(lines), highlight=False)


async def cmd_clear(app: "CopilotApp", console: Console) -> None:
    if app.session_id:
        try:
            await app.client.delete_session(app.session_id)
        except Exception:
            pass
    app.session_id = None
    app.turn_count = 0
    display.print_status("会话已清除", style="success", console=console)


async def cmd_quit(app: "CopilotApp", console: Console) -> None:
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


async def dispatch_command(app: "CopilotApp", user_input: str, console: Console = None) -> None:
    c = console or _default_console
    cmd_name = user_input.strip().split()[0].lower()
    handler = COMMANDS.get(cmd_name)
    if handler:
        await handler(app, c)
    else:
        c.print(f"  [bold yellow]未知命令: {cmd_name}，输入 /help 查看可用命令[/bold yellow]", highlight=False)
