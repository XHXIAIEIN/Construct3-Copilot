#!/usr/bin/env python3
"""
Find similar historical failure cases from tests/regressions/failure_cases.jsonl.

Usage:
  python scripts/find_similar_failures.py "toggle boolean pause"
  python scripts/find_similar_failures.py "layout parse" --top 5
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "tests" / "regressions" / "failure_cases.jsonl"


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_-]+", text.lower())
    stop = {"the", "a", "an", "and", "or", "to", "for", "with", "in", "on", "of"}
    return {w for w in words if w not in stop and len(w) > 1}


def load_cases() -> list[dict]:
    cases = []
    if not DB_PATH.exists():
        return cases
    for line in DB_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(json.loads(line))
    return cases


def score_case(query_tokens: set[str], case: dict) -> int:
    haystack = " ".join(
        [
            case.get("query", ""),
            case.get("error_signature", ""),
            case.get("root_cause", ""),
            " ".join(case.get("tags", [])),
        ]
    )
    case_tokens = tokenize(haystack)
    overlap = query_tokens & case_tokens
    return len(overlap)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Error text or user request text")
    parser.add_argument("--top", type=int, default=3, help="How many matches to print")
    args = parser.parse_args()

    cases = load_cases()
    if not cases:
        print(f"No failure case database found at: {DB_PATH}")
        return 1

    q_tokens = tokenize(args.query)
    ranked = sorted(
        ((score_case(q_tokens, case), case) for case in cases),
        key=lambda item: item[0],
        reverse=True,
    )
    ranked = [item for item in ranked if item[0] > 0][: args.top]

    if not ranked:
        print("No similar failure cases found.")
        return 2

    print(f"Found {len(ranked)} similar case(s):")
    for score, case in ranked:
        print(f"\n[{case.get('case_id')}] score={score}")
        print(f"query: {case.get('query')}")
        print(f"signature: {case.get('error_signature')}")
        print(f"root_cause: {case.get('root_cause')}")
        print(f"fix: {case.get('fix')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
