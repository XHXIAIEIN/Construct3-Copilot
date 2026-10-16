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
        if not project_path:
            return None
        p = Path(project_path)
        if not p.is_dir():
            return None
        for f in p.glob("*.c3proj"):
            return f.stem
        return None

    def build_context(self) -> dict:
        if self.project_path and self.project_name:
            return {"has_local_project": True, "project_path": self.project_path}
        return {"has_local_project": False}

    def update_from_response(self, response: dict) -> None:
        if sid := response.get("session_id"):
            self.session_id = sid
        self.turn_count += 1
