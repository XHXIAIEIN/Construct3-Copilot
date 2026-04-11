#!/usr/bin/env python3
"""
Local clipboard JSON pre-validator — no network required.

Catches structural errors (missing header, bad type, invalid eventType)
before sending to the remote Clipboard service.

Usage:
    python prevalidate.py '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
    python prevalidate.py clipboard.json

Exit codes: 0 = passed, 1 = failed or error
Output: JSON with {passed, errors, warnings} or {error}
"""
import json
import sys
from pathlib import Path

# Allow importing models from the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import ClipboardData, VALID_EVENT_TYPES  # noqa: E402


def _load_input(arg: str) -> tuple[dict | None, str | None]:
    """Parse inline JSON or read from file. Returns (data, error)."""
    stripped = arg.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped), None
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {e}"

    try:
        with open(arg, "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"File not found: {arg}"
    except json.JSONDecodeError as e:
        return None, f"File contains invalid JSON: {e}"


def prevalidate(data: dict) -> dict:
    """Validate clipboard JSON locally. Returns {passed, errors, warnings}."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Top-level structure
    try:
        ClipboardData(**data)
    except Exception as e:
        errors.append(f"Structure: {e}")
        return {"passed": False, "errors": errors, "warnings": warnings}

    # 2. If type=events, validate each item's eventType and ACE refs
    if data.get("type") == "events":
        for i, item in enumerate(data.get("items", [])):
            et = item.get("eventType")
            if et and et not in VALID_EVENT_TYPES:
                errors.append(f"items[{i}].eventType '{et}' invalid")

            # Check nested actions/conditions have required fields
            for field_name in ("conditions", "actions"):
                for j, ace in enumerate(item.get(field_name, [])):
                    if "type" not in ace:
                        errors.append(f"items[{i}].{field_name}[{j}] missing 'type'")
                    if "id" not in ace:
                        errors.append(f"items[{i}].{field_name}[{j}] missing 'id'")

    # 3. Check variables have comment field (CLAUDE.md checklist item)
    if data.get("type") == "events":
        for i, item in enumerate(data.get("items", [])):
            if item.get("eventType") == "variable" and "comment" not in item:
                warnings.append(f"items[{i}] variable missing 'comment' field")

    passed = len(errors) == 0
    return {"passed": passed, "errors": errors, "warnings": warnings}


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: prevalidate.py '<json>' | <file.json>"}))
        sys.exit(1)

    data, err = _load_input(sys.argv[1])
    if err:
        print(json.dumps({"error": err}, ensure_ascii=False))
        sys.exit(1)

    result = prevalidate(data)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
