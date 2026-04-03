"""Extract clipboard JSON from LLM reply text."""
import json
import re
from typing import Optional

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```")


def extract_clipboard_json_from_reply(reply: str) -> Optional[dict]:
    """Extract C3 clipboard JSON from an LLM reply.

    Searches code blocks first, then bare JSON. Returns the first
    dict containing "is-c3-clipboard-data": true, or None.
    """
    candidates: list[str] = []

    # Code blocks first (higher confidence)
    for m in _CODE_BLOCK_RE.finditer(reply):
        candidates.append(m.group(1).strip())

    # Bare JSON fallback — find { ... } with clipboard marker
    if "is-c3-clipboard-data" in reply:
        i = 0
        while i < len(reply):
            if reply[i] == "{":
                depth = 0
                j = i
                in_string = False
                escape = False
                while j < len(reply):
                    ch = reply[j]
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = not in_string
                    elif not in_string:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                candidates.append(reply[i : j + 1])
                                break
                    j += 1
                i = j + 1
            else:
                i += 1

    # Try parsing each candidate
    for text in candidates:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("is-c3-clipboard-data") is True:
            return data

    return None
