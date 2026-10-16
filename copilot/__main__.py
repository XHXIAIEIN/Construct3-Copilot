"""Run a local provider capability or read its persisted task result."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .runtime import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path, default=os.environ.get("COPILOT_SKILLS_ROOT") or Path(__file__).resolve().parents[2] / "Construct3-Agent-Skills")
    parser.add_argument("--data", type=Path, default=os.environ.get("COPILOT_DATA") or Path.cwd() / ".local/copilot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    show = sub.add_parser("task")
    show.add_argument("task_id")
    run = sub.add_parser("run")
    run.add_argument("name")
    run.add_argument("--project", type=Path)
    run.add_argument("--locale")
    run.add_argument("--limit", type=int)
    run.add_argument("--timeout", type=float, default=90)
    run.add_argument("--request-id")
    run.add_argument("--session", default="local")
    # Script arguments follow --, so they cannot consume the runner's own options.
    raw = sys.argv[1:]
    split = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:split])
    script_args = raw[split + 1:]
    try:
        runtime = Runtime(args.skills_root, args.data)
        if args.command == "capabilities":
            result, code = runtime.capabilities(), 0
        elif args.command == "task":
            result, code = runtime.get_task(args.task_id), 0
        else:
            result = runtime.run_script(args.name, script_args, project=args.project, locale=args.locale,
                                        limit=args.limit, timeout=args.timeout, request_id=args.request_id,
                                        session_id=args.session)
            code = {"completed": 0, "busy": 5, "timed_out": 124, "running": 75}.get(result["status"], 1)
    except (OSError, ValueError, KeyError) as exc:
        result, code = {"status": "failed", "reason": str(exc)}, 2
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
