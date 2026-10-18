"""QQ channel.

    python -m channels.qq                 connect to QQ over WebSocket (needs QQ_APPID, QQ_SECRET in channels/.env)
    python -m channels.qq --cli "问题"     ask once in the terminal, print the reply and the tool calls
"""
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="QQ channel for the Construct application")
    parser.add_argument("--cli", metavar="QUESTION", help="ask once in the terminal instead of connecting to QQ")
    parser.add_argument("--project", type=Path, help="optional folder passed to the application")
    parser.add_argument("--session", type=Path, help="with --cli: the folder a new project is made in (default sessions/cli)")
    args = parser.parse_args()

    from .. import settings as channel_settings
    from ..app import create_application
    from .bot import ask_cli, run_qq

    settings = channel_settings.load()
    data_dir = channel_settings.data_dir(settings)
    application = create_application(settings=settings, data_dir=data_dir)
    if args.cli:
        ask_cli(application, args.cli, data_dir=data_dir, project=args.project, session=args.session)
    else:
        run_qq(application, settings=settings, data_dir=data_dir)


main()
