#!/usr/bin/env python3
"""
Preflight validation for Construct 3 clipboard JSON.

Usage:
    python scripts/preflight.py input.json
    echo '{"is-c3-clipboard-data":true,...}' | python scripts/preflight.py
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_DIR = SCRIPT_DIR.parent / ".claude" / "skills" / "construct3-copilot" / "scripts"
sys.path.insert(0, str(VALIDATOR_DIR))

from validate_output import C3ClipboardValidator  # noqa: E402


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith(".json"):
            with open(arg, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = arg
    else:
        content = sys.stdin.read()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        sys.exit(1)

    validator = C3ClipboardValidator()
    is_valid = validator.validate(data)

    if is_valid:
        print("✅ Validation passed! JSON format conforms to C3 clipboard spec")
    else:
        print("❌ Validation failed! Found the following errors:")
        for error in validator.errors:
            print(f"  • {error}")

    if validator.warnings:
        print("\n⚠️  Warnings:")
        for warning in validator.warnings:
            print(f"  • {warning}")

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
