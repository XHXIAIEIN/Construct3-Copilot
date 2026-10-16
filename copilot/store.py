"""Persistent task requests and results."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DuplicateRequestError(RuntimeError):
    def __init__(self, task: dict):
        self.task = task
        super().__init__(f"Request already exists as task {task['task_id']} ({task['status']})")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, parent_id TEXT REFERENCES tasks(task_id),
                    source TEXT NOT NULL, session_id TEXT NOT NULL, capability TEXT NOT NULL,
                    request_id TEXT, digest TEXT NOT NULL, status TEXT NOT NULL,
                    request TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL, finished_at TEXT,
                    pid INTEGER NOT NULL,
                    UNIQUE(source, session_id, request_id)
                );
                CREATE INDEX IF NOT EXISTS tasks_parent ON tasks(parent_id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def create(self, capability, request, source, session_id, request_id=None, parent_id=None):
        encoded = json.dumps(request, ensure_ascii=False, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        task_id = uuid.uuid4().hex
        with self.connect() as db:
            if parent_id:
                parent = db.execute("SELECT status FROM tasks WHERE task_id=?", (parent_id,)).fetchone()
                if not parent or parent["status"] != "running":
                    raise ValueError("Parent task is absent or is no longer running")
            try:
                db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (task_id, parent_id, source, session_id, capability, request_id, digest,
                            "running", encoded, None, now(), None, os.getpid()))
            except sqlite3.IntegrityError:
                row = db.execute("SELECT task_id,digest FROM tasks WHERE source=? AND session_id=? AND request_id=?",
                                 (source, session_id, request_id)).fetchone()
                if not row:
                    raise
                if row["digest"] != digest:
                    raise ValueError("request_id was already used with different inputs") from None
                raise DuplicateRequestError(self.get(row["task_id"])) from None
        return task_id

    def finish(self, task_id, result):
        finished = now()
        result["finished_at"] = finished
        with self.connect() as db:
            changed = db.execute("UPDATE tasks SET status=?,result=?,finished_at=? WHERE task_id=? AND status='running'",
                                 (result["status"], json.dumps(result, ensure_ascii=False), finished, task_id)).rowcount
            if changed != 1:
                raise ValueError("Task was already finished or does not exist")
        return result

    def get(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise KeyError(task_id)
        task = dict(row)
        task["request"] = json.loads(task["request"])
        task["result"] = json.loads(task["result"]) if task["result"] else None
        return task

    def children(self, task_id):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT task_id FROM tasks WHERE parent_id=? ORDER BY created_at", (task_id,))]
        return [self.get(tid) for tid in ids]
