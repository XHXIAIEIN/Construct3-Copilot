#!/usr/bin/env python3
"""
Append a structured failure case into tests/regressions/failure_cases.jsonl.

Usage:
  python scripts/log_failure_case.py \
    --case-id missing-player-object \
    --query "Top-down shooter spawn bullet" \
    --signature "unknown objectClass 'Player'" \
    --root-cause "Output referenced object before definition" \
    --fix "Include object-types for Player before events" \
    --tags events,objects,dependency

Add --dry-run to preview without writing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "tests" / "regressions" / "failure_cases.jsonl"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--signature", required=True)
    p.add_argument("--root-cause", required=True)
    p.add_argument("--fix", required=True)
    p.add_argument("--tags", default="")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def load_existing_case_ids() -> set[str]:
    if not DB_PATH.exists():
        return set()
    ids: set[str] = set()
    for line in DB_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("case_id")
        if isinstance(case_id, str):
            ids.add(case_id)
    return ids


def main() -> int:
    args = parse_args()
    case_id = args.case_id.strip()
    existing = load_existing_case_ids()
    if case_id in existing:
        print(f"ERROR: case_id already exists: {case_id}")
        return 2

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    payload = {
        "case_id": case_id,
        "query": args.query.strip(),
        "error_signature": args.signature.strip(),
        "root_cause": args.root_cause.strip(),
        "fix": args.fix.strip(),
        "tags": tags,
    }

    line = json.dumps(payload, ensure_ascii=False)
    if args.dry_run:
        print(line)
        return 0

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    print(f"Appended failure case: {case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
