"""REPL loop — read input, dispatch commands or send messages."""
import asyncio
from typing import Optional

from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.clipboard import copy_json
from frontends.cli import display
from frontends.cli.commands import dispatch_command

_default_console = Console()


async def handle_message(app: CopilotApp, user_input: str, console: Console = None) -> None:
    c = console or _default_console
    context = app.build_context()

    if app.stream_enabled:
        await _handle_streaming(app, user_input, context, c)
    else:
        await _handle_sync(app, user_input, context, c)


async def _handle_sync(app: CopilotApp, message: str, context: dict, console: Console) -> None:
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


async def _handle_streaming(app: CopilotApp, message: str, context: dict, console: Console) -> None:
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
                app.update_from_response(chunk)
                _render_response(chunk, console)
                return
            else:
                display.render_stream_token(chunk, console=console)
        display.end_stream(console=console)
        app.turn_count += 1
    except KeyboardInterrupt:
        display.end_stream(console=console)
        display.print_status("输出已中断", style="warning", console=console)
    except Exception as e:
        display.end_stream(console=console)
        display.print_status(f"流式传输中断: {e}", style="error", console=console)


def _render_response(response: dict, console: Console) -> None:
    resp_type = response.get("type", "direct_answer")
    message = response.get("message", "")

    if resp_type == "error":
        display.print_status(message, style="error", console=console)
    elif resp_type == "generation":
        display.render_markdown(message, console=console)
        data = response.get("data") or {}
        clipboard_json = data.get("clipboard_json")
        if clipboard_json:
            copied = copy_json(clipboard_json)
            if copied:
                display.print_status("已复制到剪贴板", style="success", console=console)
    else:
        display.render_markdown(message, console=console)


async def run_repl(app: CopilotApp, console: Console = None) -> None:
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
