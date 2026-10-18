"""QQ channel.

    python -m channels.platforms.qq                 connect to QQ over WebSocket (needs QQ_APPID, QQ_SECRET in channels/.env)
    python -m channels.platforms.qq --cli "问题"     ask once in the terminal, print the reply and the tool calls
"""
from ...core import entry


def run(application, **kwargs) -> None:
    from .bot import run_qq  # botpy is imported only to connect
    run_qq(application, **kwargs)


def split(text: str) -> list[str]:
    from .bot import chunks
    return chunks(text)


entry.main("qq", run, split=split, description="QQ channel for the application channels/app.py makes")
