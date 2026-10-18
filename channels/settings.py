"""Read channels/.env once, at the entry point, into a dict that is passed on explicitly.

The process environment wins over .env, as load_dotenv without override did: the panel starts a channel with the
managed keys removed from its environment, so the channel reads them from .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

HOME = Path(__file__).resolve().parent  # channels/: .env and var/
REPO = HOME.parent  # the Copilot checkout: .venv/, copilot/


def load(home: Path = HOME) -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(home / ".env").items() if v is not None}
    values.update(os.environ)
    return values


def data_dir(settings: dict, home: Path = HOME) -> Path:
    """Everything the channels write while they run: logs/, sessions/, copilot/, runtime/, backups/."""
    configured = settings.get("QQBOT_DATA") or settings.get("C3BOT_DATA")
    return (home / configured).resolve() if configured else home / "var"
