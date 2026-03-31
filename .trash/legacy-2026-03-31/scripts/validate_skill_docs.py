#!/usr/bin/env python3
"""
Validate skill documentation quality gates for Construct3-Copilot.

Checks:
1) Markdown links to local JSON files resolve.
2) Clipboard JSON examples in canonical docs parse and pass validate_output.py checks.
3) Known bad ACE IDs are blocked in paste-ready JSON examples.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "construct3-copilot"
VALIDATOR_PATH = SKILL_DIR / "scripts" / "validate_output.py"

# Canonical docs intended to provide paste-ready examples.
CANONICAL_DOCS = [
    SKILL_DIR / "references" / "examples.md",
    SKILL_DIR / "references" / "layout-templates.md",
    SKILL_DIR / "references" / "effects-guide.md",
    SKILL_DIR / "references" / "family-patterns.md",
]

BANNED_ACE_IDS = {
    "set-angle-toward-position",
    "toggle-boolean",
    "compare-boolean",
    "add-to",
}


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_output", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator module: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_json_code_blocks(text: str) -> list[str]:
    return [
        m.group(1).strip()
        for m in re.finditer(r"[ \t]*```json(?!c)\r?\n(.*?)\r?\n[ \t]*```", text, flags=re.S)
    ]


def iter_local_links(doc_text: str) -> Iterable[str]:
    for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", doc_text):
        target = m.group(1).strip()
        if not target or target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        yield target


def collect_ace_ids(node) -> Iterable[str]:
    if isinstance(node, dict):
        ace = node.get("id")
        if isinstance(ace, str):
            yield ace
        for value in node.values():
            yield from collect_ace_ids(value)
    elif isinstance(node, list):
        for item in node:
            yield from collect_ace_ids(item)


def main() -> int:
    mod = load_validator_module()
    errors: list[str] = []
    checked_blocks = 0

    for doc in CANONICAL_DOCS:
        if not doc.exists():
            errors.append(f"[missing-doc] {doc}")
            continue

        text = doc.read_text(encoding="utf-8")

        # Link checks for JSON resources referenced in docs.
        for link in iter_local_links(text):
            if not link.endswith(".json"):
                continue
            resolved = (doc.parent / link).resolve()
            if not resolved.exists():
                errors.append(f"[missing-link] {doc}: {link}")

        # Clipboard JSON block checks.
        for idx, block in enumerate(extract_json_code_blocks(text), start=1):
            if "is-c3-clipboard-data" not in block:
                continue

            checked_blocks += 1
            try:
                payload = json.loads(block)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"[json-parse] {doc} block#{idx}: {exc}")
                continue

            validator = mod.C3ClipboardValidator()
            if not validator.validate(payload):
                msg = "; ".join(validator.errors[:3])
                errors.append(f"[clipboard-invalid] {doc} block#{idx}: {msg}")

            bad = sorted(set(ace for ace in collect_ace_ids(payload) if ace in BANNED_ACE_IDS))
            if bad:
                errors.append(f"[banned-ace] {doc} block#{idx}: {', '.join(bad)}")

    if errors:
        print("Skill docs validation FAILED")
        for line in errors:
            print(f" - {line}")
        return 1

    print(f"Skill docs validation PASSED (checked clipboard blocks: {checked_blocks})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
