"""What every platform's python -m entry does: read the settings, make the application on the configured model,
then connect to the platform, or with --cli ask once in the terminal.

    python -m channels.platforms.<name>                 connect (the platform's credentials in channels/.env)
    python -m channels.platforms.<name> --cli "问题"     ask once, print the reply and the tool calls
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .answers import handle, AnswerLog, file_fact
from .chat import size_of


def main(channel: str, run, *, split=lambda text: [text], description: str | None = None) -> None:
    """run(application, settings=, data_dir=, usage=) connects to the platform; split(text) is how the platform
    cuts a reply into messages, which --cli prints."""
    parser = argparse.ArgumentParser(description=description or f"{channel} channel for the application channels/app.py makes")
    parser.add_argument("--cli", metavar="QUESTION", help=f"ask once in the terminal instead of connecting to {channel}")
    parser.add_argument("--project", type=Path, help="optional folder passed to the application")
    parser.add_argument("--session", type=Path, help="with --cli: the folder a new project is made in (default sessions/cli)")
    args = parser.parse_args()

    from .. import settings as channel_settings
    from ..app import create_application
    from ..model.usage import Usage

    settings = channel_settings.load()
    data_dir = channel_settings.data_dir(settings)
    usage = Usage(data_dir)
    application = create_application(settings=settings, data_dir=data_dir, usage=usage)
    if args.cli:
        ask_cli(application, args.cli, channel=channel, data_dir=data_dir, project=args.project,
                session=args.session, usage=usage, split=split)
    else:
        run(application, settings=settings, data_dir=data_dir, usage=usage)


def ask_cli(application, question: str, *, channel: str, data_dir: Path, project: Path | None = None,
            session: Path | None = None, usage=None, split=lambda text: [text]) -> None:
    """Ask once in the terminal; print the tool calls, the reply as the platform would split it, and the files.
    The answer goes to the platform's answer log as chat "cli", its files as not sent; the gateway receipt is the
    running platform's and is left alone."""
    answer = handle(application, {
        "text": question, "session_id": "cli", "session_dir": session or data_dir / "sessions" / "cli",
        "history": [], "group": False, "attachments": [], "project": project,
        "notify": lambda note: print(f"[note] {note}")}, usage=usage)
    result = answer.result
    AnswerLog(data_dir, channel).write(
        answer, chat="cli", session="cli", files_in=[],
        files_out=[file_fact(Path(p).name, size_of(Path(p)), sent=False) for p in result.get("files", [])])
    if answer.error is not None:
        raise answer.error
    for trace in result.get("trace", []): print(f"[tool] {trace}")
    print("\n=====\n".join(split(result.get("text", ""))))
    for path in result.get("files", []): print(f"[file] {path}")
