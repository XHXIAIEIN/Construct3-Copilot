"""Record QQ gateway startup and ready events."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GatewayReceipt:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "runtime" / "gateway.json"
        self.pid = os.getpid()
        self.record: dict | None = None

    def starting(self) -> None:
        self.record = {"status": "starting", "pid": self.pid, "started_at": utc_now()}
        self._write()

    def ready(self) -> None:
        if self.record is None:
            raise RuntimeError("Record gateway startup before its ready event")
        self.record.update(status="ready", ready_at=utc_now())
        self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        draft = self.path.with_name(f".{self.path.name}.{self.pid}.tmp")
        draft.write_text(json.dumps(self.record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(draft, self.path)
