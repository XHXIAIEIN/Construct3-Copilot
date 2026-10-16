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
        import pyreadline3  # noqa: F401
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
