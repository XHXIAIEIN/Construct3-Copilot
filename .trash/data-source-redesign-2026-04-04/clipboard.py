#!/usr/bin/env python3
"""
Intent IR → Construct 3 Clipboard JSON Generator

Converts structured intent (gameplay, ui, assets) into paste-ready C3 clipboard JSON.
This handles the deterministic parts of generation; LLM reasoning is done by Claude Code.

Usage:
    echo '{"gameplay":["WASD movement"],"assets":["Player"]}' | python clipboard.py
    python clipboard.py intent.json
"""

import json
import sys


def generate_from_intent(intent: dict) -> dict:
    """Convert an Intent IR dict to a C3 clipboard JSON structure.

    This is a scaffold — the actual generation logic will map intent fields
    to clipboard templates using the reference data in references/.

    Returns a clipboard-format dict ready for validate/output.py.
    """
    # TODO: implement template-based generation
    # 1. Map assets to object-types (with imageData from generate/imagedata.py)
    # 2. Map gameplay descriptions to event blocks (using query/schema.py for ACE IDs)
    # 3. Map ui descriptions to Text/UI objects
    # 4. Assemble into clipboard JSON

    return {
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [],
        "_meta": {
            "generator": "clipboard.py",
            "status": "skeleton",
            "intent": intent,
        },
    }


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
        intent = json.loads(content)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    result = generate_from_intent(intent)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
