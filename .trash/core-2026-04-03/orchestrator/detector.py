"""Clipboard JSON detection for Construct 3 Copilot."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DetectionResult:
    found: bool
    clipboard_json: Optional[dict] = None
    clipboard_type: Optional[str] = None
    user_instruction: str = ""
    raw_json_str: Optional[str] = None


def _extract_bare_json_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) index spans of top-level { ... } blocks in text.

    Uses brace counting with proper string and escape handling so nested
    objects don't cause false positives or truncation.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        # Found a potential JSON start
        start = i
        depth = 0
        in_string = False
        j = i
        while j < n:
            ch = text[j]
            if in_string:
                if ch == "\\":
                    j += 2  # skip escaped char
                    continue
                if ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        spans.append((start, j + 1))
                        i = j + 1
                        break
            j += 1
        else:
            # Never closed
            break
    return spans


def detect_clipboard_json(message: str) -> DetectionResult:
    """Detect a Construct 3 clipboard JSON block embedded in a user message.

    Returns a DetectionResult.  Only JSON objects that contain
    ``"is-c3-clipboard-data": true`` are considered clipboard data.
    """
    # Fast path: avoid any parsing when the sentinel string is absent
    if "is-c3-clipboard-data" not in message:
        return DetectionResult(found=False, user_instruction=message)

    candidates: list[tuple[str, int, int]] = []  # (json_str, start, end)

    # 1. Code-fence blocks: ```json ... ``` or ``` ... ```
    code_block_re = re.compile(
        r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL
    )
    for m in code_block_re.finditer(message):
        candidates.append((m.group(1).strip(), m.start(), m.end()))

    # 2. Bare { ... } spans (skip positions already covered by code blocks)
    code_ranges = [(s, e) for (_, s, e) in candidates]

    for start, end in _extract_bare_json_spans(message):
        # Skip if this span is inside a code block we already captured
        inside_code = any(cs <= start and end <= ce for cs, ce in code_ranges)
        if not inside_code:
            candidates.append((message[start:end], start, end))

    # 3. Try each candidate; first valid clipboard JSON wins
    for raw, span_start, span_end in candidates:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue
        if obj.get("is-c3-clipboard-data") is not True:
            continue

        # Found it — build user_instruction from text outside this span
        # For code-block candidates the span covers the fences too, which is
        # what we want to strip out.
        instruction = (message[:span_start] + message[span_end:]).strip()

        return DetectionResult(
            found=True,
            clipboard_json=obj,
            clipboard_type=obj.get("type"),
            user_instruction=instruction,
            raw_json_str=raw,
        )

    return DetectionResult(found=False, user_instruction=message)
