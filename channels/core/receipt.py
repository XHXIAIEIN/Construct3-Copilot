"""Record the gateway's startup and ready events, and how many answers it is giving."""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .codestamp import CodeStamp


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GatewayReceipt:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "runtime" / "gateway.json"
        self.pid = os.getpid()
        self.code = CodeStamp().stamp()  # once, as the process starts: the code it has imported
        self.record: dict | None = None
        self._lock = threading.Lock()  # answers run in worker threads

    def starting(self) -> None:
        with self._lock:
            self.record = {"status": "starting", "pid": self.pid, "started_at": utc_now(), "active_answers": 0,
                           "code": self.code}
            self._write()

    def ready(self) -> None:
        with self._lock:
            if self.record is None:
                raise RuntimeError("Record gateway startup before its ready event")
            self.record.update(status="ready", ready_at=utc_now())
            self._write()

    @contextmanager
    def answering(self):
        """Count an answer as active while the application handles it: the panel switches models only when
        none is, and it trusts the count only while this process is alive."""
        self._add(1)
        try:
            yield
        finally:
            self._add(-1)

    def _add(self, step: int) -> None:
        with self._lock:
            if self.record is None:
                raise RuntimeError("Record gateway startup before its answers")
            self.record["active_answers"] = max(0, self.record.get("active_answers", 0) + step)
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        draft = self.path.with_name(f".{self.path.name}.{self.pid}.tmp")
        draft.write_text(json.dumps(self.record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(draft, self.path)
