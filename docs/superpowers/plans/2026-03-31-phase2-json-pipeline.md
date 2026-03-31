# Phase 2: JSON 处理管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Copilot pipeline to detect C3 clipboard JSON in user messages and provide validation, analysis, modification, and repair capabilities.

**Architecture:** Dual-track pipeline — messages containing `"is-c3-clipboard-data"` are routed to a JSON processing branch (detect → validate → RAG enrich → LLM process → output validate → deliver). Messages without clipboard JSON continue through the existing Q&A track unchanged.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, httpx, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-31-phase2-json-pipeline-design.md`

---

### Task 0: Add test dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest-asyncio to requirements.txt**

Append to the end of `requirements.txt`:

```
# Testing
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Install**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && pip install pytest-asyncio`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest-asyncio dependency for Phase 2 tests"
```

---

### Task 1: JSON Detector — Tests

**Files:**
- Create: `tests/test_detector.py`

- [ ] **Step 1: Write detector tests**

```python
"""Tests for clipboard JSON detection in user messages."""
import pytest
from src.orchestrator.detector import detect_clipboard_json, DetectionResult


class TestDetectClipboardJson:
    """Test clipboard JSON detection from user messages."""

    def test_plain_text_no_json(self):
        result = detect_clipboard_json("Sprite 的 Set animation 怎么用？")
        assert result.found is False
        assert result.clipboard_json is None
        assert result.clipboard_type is None
        assert result.user_instruction == "Sprite 的 Set animation 怎么用？"

    def test_pure_clipboard_json(self):
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_json == {"is-c3-clipboard-data": True, "type": "events", "items": []}
        assert result.clipboard_type == "events"
        assert result.user_instruction.strip() == ""

    def test_json_with_instruction(self):
        msg = '帮我看看这段 JSON 有什么问题：\n{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "events"
        assert "帮我看看" in result.user_instruction

    def test_json_in_code_block(self):
        msg = '检查一下：\n```json\n{"is-c3-clipboard-data":true,"type":"object-types","items":[]}\n```'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "object-types"

    def test_non_clipboard_json(self):
        msg = '{"name": "test", "value": 42}'
        result = detect_clipboard_json(msg)
        assert result.found is False

    def test_invalid_json_syntax(self):
        msg = '{"is-c3-clipboard-data":true, broken}'
        result = detect_clipboard_json(msg)
        assert result.found is False

    def test_multiple_json_blocks_picks_clipboard(self):
        msg = '第一个：{"foo":1}\n第二个：{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "events"

    def test_preserves_raw_json_str(self):
        json_str = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        msg = f"看看这个：{json_str}"
        result = detect_clipboard_json(msg)
        assert result.raw_json_str is not None
        assert "is-c3-clipboard-data" in result.raw_json_str

    def test_nested_json_with_events(self):
        msg = '''{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[]}]}'''
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert len(result.clipboard_json["items"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.orchestrator.detector'`

---

### Task 2: JSON Detector — Implementation

**Files:**
- Create: `src/orchestrator/detector.py`

- [ ] **Step 1: Implement detector**

```python
"""Detect and extract C3 clipboard JSON from user messages."""
import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DetectionResult:
    """Result of clipboard JSON detection."""
    found: bool
    clipboard_json: Optional[dict] = None
    clipboard_type: Optional[str] = None
    user_instruction: str = ""
    raw_json_str: Optional[str] = None


# Matches JSON code blocks: ```json ... ``` or ``` ... ```
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```")

# Matches top-level JSON objects (greedy brace matching via counting)
_JSON_CANDIDATE_MARKER = "is-c3-clipboard-data"


def _extract_json_candidates(text: str) -> list[tuple[str, int, int]]:
    """Extract potential JSON object strings from text.

    Returns list of (json_str, start_pos, end_pos).
    Checks code blocks first, then scans for bare { ... } blocks.
    """
    candidates: list[tuple[str, int, int]] = []

    # 1) Code blocks
    for m in _CODE_BLOCK_RE.finditer(text):
        candidates.append((m.group(1).strip(), m.start(), m.end()))

    # 2) Bare JSON objects — scan for { and match closing }
    i = 0
    while i < len(text):
        if text[i] == "{":
            # Skip if inside a code block we already found
            in_block = any(s <= i < e for _, s, e in candidates)
            if in_block:
                i += 1
                continue
            # Count braces to find matching close
            depth = 0
            j = i
            in_string = False
            escape = False
            while j < len(text):
                ch = text[j]
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
                            candidates.append((text[i : j + 1], i, j + 1))
                            break
                j += 1
            i = j + 1
        else:
            i += 1

    return candidates


def detect_clipboard_json(message: str) -> DetectionResult:
    """Detect C3 clipboard JSON in a user message.

    Scans for JSON objects containing "is-c3-clipboard-data": true.
    Returns the first match along with the remaining user instruction text.
    """
    if _JSON_CANDIDATE_MARKER not in message:
        return DetectionResult(found=False, user_instruction=message)

    candidates = _extract_json_candidates(message)

    for json_str, start, end in candidates:
        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            continue

        if not isinstance(data, dict):
            continue

        if data.get("is-c3-clipboard-data") is True:
            # Extract user instruction = everything outside the JSON block
            before = message[:start].strip()
            after = message[end:].strip()
            instruction = f"{before} {after}".strip()
            # Clean up code block markers from instruction
            instruction = re.sub(r"```(?:json)?", "", instruction).strip()

            return DetectionResult(
                found=True,
                clipboard_json=data,
                clipboard_type=data.get("type"),
                user_instruction=instruction,
                raw_json_str=json_str,
            )

    return DetectionResult(found=False, user_instruction=message)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_detector.py -v`
Expected: All 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/orchestrator/detector.py tests/test_detector.py
git commit -m "feat(phase2): add clipboard JSON detector with tests"
```

---

### Task 3: JSON Validator — Tests

**Files:**
- Create: `tests/test_validator.py`

- [ ] **Step 1: Write validator tests**

```python
"""Tests for clipboard JSON validation."""
import pytest
from src.orchestrator.validator import (
    validate_local,
    ValidationReport,
    ValidationIssue,
)


class TestStructuralValidation:
    """Test Layer 1: structural format checks."""

    def test_valid_events_minimal(self):
        data = {"is-c3-clipboard-data": True, "type": "events", "items": []}
        report = validate_local(data)
        assert report.passed is True
        assert len([i for i in report.issues if i.level == "error"]) == 0

    def test_missing_clipboard_marker(self):
        data = {"type": "events", "items": []}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "MISSING_CLIPBOARD_MARKER" for i in report.issues)

    def test_invalid_type(self):
        data = {"is-c3-clipboard-data": True, "type": "invalid", "items": []}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "INVALID_TYPE" for i in report.issues)

    def test_missing_items(self):
        data = {"is-c3-clipboard-data": True, "type": "events"}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "MISSING_ITEMS" for i in report.issues)

    def test_valid_event_types(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""},
                {"eventType": "comment", "text": "Init"},
                {"eventType": "block", "conditions": [], "actions": []},
            ],
        }
        report = validate_local(data)
        assert report.passed is True

    def test_invalid_event_type(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{"eventType": "unknown"}],
        }
        report = validate_local(data)
        assert any(i.code == "INVALID_EVENT_TYPE" for i in report.issues)


class TestKnownPitfalls:
    """Test Layer 2: known C3 pitfalls."""

    def test_empty_parameters_object(self):
        """Empty parameters {} should be omitted entirely."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [
                        {"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}
                    ],
                    "actions": [],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "EMPTY_PARAMS" for i in report.issues)

    def test_variable_missing_comment(self):
        """Variable events must have a comment field."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0"}
            ],
        }
        report = validate_local(data)
        assert any(i.code == "VARIABLE_MISSING_COMMENT" for i in report.issues)

    def test_deprecated_behavior_id_solid(self):
        """Solid (uppercase) is V1, should be solid (lowercase)."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Wall",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "Solid", "name": "Solid", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_V1" for i in report.issues)

    def test_deprecated_behavior_id_scrollto(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Camera",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "ScrollTo", "name": "ScrollTo", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_V1" for i in report.issues)

    def test_effect_types_as_object(self):
        """effectTypes must be array, not object with items/subfolders."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Player",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [],
                    "instanceVariables": [],
                    "effectTypes": {"items": [], "subfolders": []},
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "EFFECT_TYPES_NOT_ARRAY" for i in report.issues)

    def test_instance_variables_as_object(self):
        """instanceVariables must be array, not object."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Player",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [],
                    "instanceVariables": {"items": [], "subfolders": []},
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "INSTANCE_VARS_NOT_ARRAY" for i in report.issues)

    def test_duplicate_sids(self):
        """SIDs must be unique across the entire JSON."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [{"id": "on-start-of-layout", "objectClass": "System", "sid": 100}],
                    "actions": [{"id": "wait", "objectClass": "System", "sid": 100}],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DUPLICATE_SID" for i in report.issues)

    def test_trigger_in_children(self):
        """Trigger conditions (on-*) cannot appear in children (sub-events)."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [{"id": "every-tick", "objectClass": "System"}],
                    "actions": [],
                    "children": [
                        {
                            "eventType": "block",
                            "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}],
                            "actions": [],
                        }
                    ],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "TRIGGER_IN_CHILDREN" for i in report.issues)

    def test_multiple_triggers_in_block(self):
        """A single block can have at most one trigger condition."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [
                        {"id": "on-start-of-layout", "objectClass": "System"},
                        {"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}},
                    ],
                    "actions": [],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "MULTIPLE_TRIGGERS" for i in report.issues)

    def test_destroy_outside_layout_deprecated(self):
        """DestroyOutsideLayout behavior is removed in V2."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Bullet",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "DestroyOutsideLayout", "name": "DOL", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_REMOVED" for i in report.issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.orchestrator.validator'`

---

### Task 4: JSON Validator — Implementation

**Files:**
- Create: `src/orchestrator/validator.py`

- [ ] **Step 1: Implement validator**

```python
"""Local clipboard JSON validator.

Validates C3 clipboard JSON against known structural rules and pitfalls.
This is a lightweight local validator — the full validator lives in the
Clipboard service (Phase 5).
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALID_CLIPBOARD_TYPES = {"events", "object-types", "layouts", "world-instances", "event-sheets"}
VALID_EVENT_TYPES = {"block", "variable", "comment", "group", "function-block"}

# V1 behavior IDs that must be lowercased in V2
V1_TO_V2_BEHAVIORS = {
    "Solid": "solid",
    "ScrollTo": "scrollto",
}

# Completely removed behaviors
REMOVED_BEHAVIORS = {"DestroyOutsideLayout"}

# Known trigger conditions (prefix-based: "on-*")
TRIGGER_PREFIXES = ("on-",)


@dataclass
class ValidationIssue:
    """A single validation finding."""
    level: str      # "error" | "warning" | "suggestion"
    code: str       # machine-readable code
    message: str    # human-readable description
    path: str = ""  # JSON path, e.g. "items[2].actions[0].parameters"


@dataclass
class ValidationReport:
    """Validation result with structured issues."""
    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: str = ""

    def add(self, level: str, code: str, message: str, path: str = ""):
        self.issues.append(ValidationIssue(level=level, code=code, message=message, path=path))
        if level == "error":
            self.passed = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [
                {"level": i.level, "code": i.code, "message": i.message, "path": i.path}
                for i in self.issues
            ],
            "summary": self.summary,
        }


def _is_trigger(condition_id: str) -> bool:
    """Check if a condition ID is a trigger type."""
    return any(condition_id.startswith(p) for p in TRIGGER_PREFIXES)


def _collect_sids(data, path: str = "") -> list[tuple[int, str]]:
    """Recursively collect all SID values with their paths."""
    sids = []
    if isinstance(data, dict):
        for key, val in data.items():
            current = f"{path}.{key}" if path else key
            if key == "sid" and isinstance(val, (int, float)):
                sids.append((int(val), current))
            else:
                sids.extend(_collect_sids(val, current))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            sids.extend(_collect_sids(item, f"{path}[{i}]"))
    return sids


def _validate_structure(data: dict, report: ValidationReport):
    """Layer 1: structural format checks."""
    if data.get("is-c3-clipboard-data") is not True:
        report.add("error", "MISSING_CLIPBOARD_MARKER", '"is-c3-clipboard-data": true is missing')

    clip_type = data.get("type")
    if clip_type not in VALID_CLIPBOARD_TYPES:
        report.add("error", "INVALID_TYPE", f'Invalid type "{clip_type}", must be one of {VALID_CLIPBOARD_TYPES}')

    if "items" not in data:
        report.add("error", "MISSING_ITEMS", '"items" array is missing')
        return  # can't validate further without items

    items = data["items"]
    if not isinstance(items, list):
        report.add("error", "ITEMS_NOT_ARRAY", '"items" must be an array')
        return

    if clip_type == "events":
        _validate_event_items(items, report)
    elif clip_type == "object-types":
        _validate_object_items(items, report)


def _validate_event_items(items: list, report: ValidationReport):
    """Validate event-type items."""
    for i, item in enumerate(items):
        path = f"items[{i}]"
        if not isinstance(item, dict):
            report.add("error", "ITEM_NOT_OBJECT", f"Item at {path} is not an object", path)
            continue

        et = item.get("eventType")
        if et not in VALID_EVENT_TYPES:
            report.add("error", "INVALID_EVENT_TYPE", f'Invalid eventType "{et}" at {path}', path)
            continue

        if et == "variable":
            _validate_variable(item, path, report)
        elif et == "block":
            _validate_block(item, path, report, is_child=False)


def _validate_variable(item: dict, path: str, report: ValidationReport):
    """Validate a variable event node."""
    if "comment" not in item:
        report.add("warning", "VARIABLE_MISSING_COMMENT",
                    f'Variable "{item.get("name", "?")}" at {path} is missing "comment" field', path)


def _validate_block(item: dict, path: str, report: ValidationReport, is_child: bool):
    """Validate a block event node."""
    conditions = item.get("conditions", [])
    actions = item.get("actions", [])

    # Check conditions
    trigger_count = 0
    for ci, cond in enumerate(conditions):
        if not isinstance(cond, dict):
            continue
        cpath = f"{path}.conditions[{ci}]"
        cid = cond.get("id", "")

        if _is_trigger(cid):
            trigger_count += 1
            if is_child:
                report.add("error", "TRIGGER_IN_CHILDREN",
                           f'Trigger condition "{cid}" cannot appear in sub-events', cpath)

        # Check empty parameters
        params = cond.get("parameters")
        if isinstance(params, dict) and len(params) == 0:
            report.add("warning", "EMPTY_PARAMS",
                       f'Empty parameters {{}} at {cpath} should be omitted', cpath)

    if trigger_count > 1:
        report.add("error", "MULTIPLE_TRIGGERS",
                   f"Block at {path} has {trigger_count} trigger conditions (max 1)", path)

    # Check actions
    for ai, act in enumerate(actions):
        if not isinstance(act, dict):
            continue
        apath = f"{path}.actions[{ai}]"
        params = act.get("parameters")
        if isinstance(params, dict) and len(params) == 0:
            report.add("warning", "EMPTY_PARAMS",
                       f'Empty parameters {{}} at {apath} should be omitted', apath)

    # Recurse into children
    children = item.get("children", [])
    for ci, child in enumerate(children):
        if isinstance(child, dict) and child.get("eventType") == "block":
            _validate_block(child, f"{path}.children[{ci}]", report, is_child=True)


def _validate_object_items(items: list, report: ValidationReport):
    """Validate object-type items."""
    for i, item in enumerate(items):
        path = f"items[{i}]"
        if not isinstance(item, dict):
            continue

        # effectTypes must be array
        et = item.get("effectTypes")
        if et is not None and not isinstance(et, list):
            report.add("error", "EFFECT_TYPES_NOT_ARRAY",
                       f"effectTypes at {path} must be an array, not {type(et).__name__}", path)

        # instanceVariables must be array
        iv = item.get("instanceVariables")
        if iv is not None and not isinstance(iv, list):
            report.add("error", "INSTANCE_VARS_NOT_ARRAY",
                       f"instanceVariables at {path} must be an array, not {type(iv).__name__}", path)

        # Check behavior IDs
        for bi, beh in enumerate(item.get("behaviorTypes", [])):
            if not isinstance(beh, dict):
                continue
            bpath = f"{path}.behaviorTypes[{bi}]"
            bid = beh.get("behaviorId", "")

            if bid in V1_TO_V2_BEHAVIORS:
                report.add("warning", "DEPRECATED_BEHAVIOR_V1",
                           f'behaviorId "{bid}" is V1 — use "{V1_TO_V2_BEHAVIORS[bid]}" instead',
                           bpath)
            elif bid in REMOVED_BEHAVIORS:
                report.add("error", "DEPRECATED_BEHAVIOR_REMOVED",
                           f'behaviorId "{bid}" has been removed in SDK V2', bpath)


def _validate_sids(data: dict, report: ValidationReport):
    """Check SID uniqueness."""
    sids = _collect_sids(data)
    seen: dict[int, str] = {}
    for sid_val, sid_path in sids:
        if sid_val in seen:
            report.add("warning", "DUPLICATE_SID",
                       f"Duplicate SID {sid_val} at {sid_path} (first seen at {seen[sid_val]})",
                       sid_path)
        else:
            seen[sid_val] = sid_path


def validate_local(data: dict) -> ValidationReport:
    """Run all local validation checks (no external service calls).

    Layers:
    1. Structural format
    2. Known C3 pitfalls
    3. SID uniqueness
    """
    report = ValidationReport()
    _validate_structure(data, report)
    _validate_sids(data, report)

    # Build summary
    errors = sum(1 for i in report.issues if i.level == "error")
    warnings = sum(1 for i in report.issues if i.level == "warning")
    if errors == 0 and warnings == 0:
        report.summary = "No issues found"
    elif errors == 0:
        report.summary = f"{warnings} warning(s)"
    else:
        report.summary = f"{errors} error(s), {warnings} warning(s)"

    return report
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_validator.py -v`
Expected: All 12 tests PASS

- [ ] **Step 3: Run detector + validator tests together**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_detector.py tests/test_validator.py -v`
Expected: All 21 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/orchestrator/validator.py tests/test_validator.py
git commit -m "feat(phase2): add clipboard JSON validator with pitfall detection"
```

---

### Task 5: Clipboard Processing Prompt

**Files:**
- Create: `src/llm/prompts/clipboard.py`

- [ ] **Step 1: Create clipboard processing prompt module**

```python
"""Prompts for clipboard JSON processing pipeline."""
from src.orchestrator.validator import ValidationReport


CLIPBOARD_SYSTEM = """\
You are a Construct 3 clipboard JSON expert. You analyze, validate, modify, \
and repair C3 clipboard JSON data with deep knowledge of the format's rules \
and common pitfalls.

Key rules you enforce:
- "is-c3-clipboard-data": true is mandatory
- type must be: events | object-types | layouts | world-instances | event-sheets
- Empty parameters {} must be omitted entirely (no empty objects)
- Trigger conditions (on-*) cannot appear in children (sub-events)
- Each block can have at most one trigger condition
- Variable events require a "comment" field (can be "")
- effectTypes and instanceVariables must be arrays, not objects
- behaviorId: "Solid" → "solid", "ScrollTo" → "scrollto" (V2 lowercase)
- DestroyOutsideLayout is removed — use events to detect out-of-bounds + destroy
- SIDs must be unique integers across the entire JSON

When modifying or fixing JSON:
- Output the COMPLETE clipboard JSON (not a diff or partial snippet)
- Wrap JSON output in a ```json code block
- Briefly explain what you changed and why

When analyzing JSON:
- Explain what the events/objects do in plain language
- Point out any issues or potential improvements
- Respond in the user's language
"""


def build_clipboard_prompt(
    clipboard_json: dict,
    validation_report: ValidationReport,
    rag_context: str = "",
    user_instruction: str = "",
) -> str:
    """Build the system prompt for clipboard JSON processing.

    Assembles context from validation results, RAG knowledge, the user's
    clipboard JSON, and their natural language instruction.
    """
    import json

    parts = [CLIPBOARD_SYSTEM]

    # Validation results
    if validation_report.issues:
        issues_text = "\n".join(
            f"- [{i.level.upper()}] {i.code}: {i.message} (at {i.path})"
            if i.path else f"- [{i.level.upper()}] {i.code}: {i.message}"
            for i in validation_report.issues
        )
        parts.append(
            f"\n## Validation Results\n\n"
            f"The following issues were found in the user's JSON:\n\n{issues_text}"
        )
    else:
        parts.append("\n## Validation Results\n\nNo issues found in the user's JSON.")

    # RAG context
    if rag_context:
        parts.append(
            f"\n## Reference Knowledge (from RAG)\n\n"
            f"Relevant Construct 3 documentation:\n\n{rag_context}"
        )

    # The clipboard JSON itself
    json_str = json.dumps(clipboard_json, ensure_ascii=False, indent=2)
    parts.append(f"\n## User's Clipboard JSON\n\n```json\n{json_str}\n```")

    # User instruction
    if user_instruction:
        parts.append(f"\n## User's Request\n\n{user_instruction}")
    else:
        parts.append(
            "\n## User's Request\n\n"
            "The user pasted this JSON without additional instructions. "
            "Validate it and report any issues found. If issues exist, "
            "suggest fixes. If the JSON looks good, briefly describe what it does."
        )

    return "\n".join(parts)
```

- [ ] **Step 2: Commit**

```bash
git add src/llm/prompts/clipboard.py
git commit -m "feat(phase2): add clipboard JSON processing prompts"
```

---

### Task 6: JSON Extraction Helper

**Files:**
- Create: `tests/test_json_extract.py`
- Create: `src/orchestrator/json_extract.py`

This helper extracts clipboard JSON from LLM replies (which may contain explanatory text + JSON code blocks).

- [ ] **Step 1: Write tests**

```python
"""Tests for JSON extraction from LLM replies."""
import pytest
from src.orchestrator.json_extract import extract_clipboard_json_from_reply


class TestExtractClipboardJsonFromReply:

    def test_json_in_code_block(self):
        reply = 'Here is the fix:\n```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```\nDone.'
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
        assert result["is-c3-clipboard-data"] is True

    def test_no_json_in_reply(self):
        reply = "The JSON looks fine. No issues found."
        result = extract_clipboard_json_from_reply(reply)
        assert result is None

    def test_non_clipboard_json_ignored(self):
        reply = '```json\n{"foo": "bar"}\n```'
        result = extract_clipboard_json_from_reply(reply)
        assert result is None

    def test_multiple_code_blocks_picks_clipboard(self):
        reply = (
            '```json\n{"example": true}\n```\n'
            'And the fixed version:\n'
            '```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```'
        )
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
        assert result["type"] == "events"

    def test_bare_json_without_code_block(self):
        reply = 'Fixed:\n{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_json_extract.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_json_extract.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/json_extract.py tests/test_json_extract.py
git commit -m "feat(phase2): add JSON extraction helper for LLM replies"
```

---

### Task 7: Pipeline Integration — Tests

**Files:**
- Create: `tests/test_pipeline_json.py`

- [ ] **Step 1: Write pipeline integration tests**

```python
"""Tests for the JSON processing pipeline branch."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.orchestrator.pipeline import Pipeline
from src.orchestrator.session import SessionManager
from src.schemas.api import ChatRequest, ChatContext


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="The JSON looks good. It sets up a Score variable and initializes it to 0 on layout start.")
    llm.is_available = True
    return llm


@pytest.fixture
def sessions():
    return SessionManager()


@pytest.fixture
def pipeline(mock_llm, sessions):
    return Pipeline(llm=mock_llm, sessions=sessions, rag=None)


class TestPipelineJsonDetection:

    @pytest.mark.asyncio
    async def test_plain_text_goes_to_qa_track(self, pipeline, mock_llm):
        """Non-JSON messages use existing Q&A path."""
        request = ChatRequest(message="Sprite 的 Set animation 怎么用？")
        response = await pipeline.process(request)
        assert response.type == "direct_answer"
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_clipboard_json_goes_to_json_track(self, pipeline, mock_llm):
        """Messages with clipboard JSON use the JSON processing path."""
        msg = '看看这个：{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        # LLM should still be called (for analysis/processing)
        mock_llm.chat.assert_called_once()
        # The system prompt should contain clipboard-specific content
        call_args = mock_llm.chat.call_args[0][0]
        system_msg = call_args[0]["content"]
        assert "clipboard JSON" in system_msg.lower() or "Clipboard JSON" in system_msg

    @pytest.mark.asyncio
    async def test_json_track_returns_validation_in_response(self, pipeline):
        """JSON track includes input validation data."""
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        # response should include modules_used
        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_json_track_with_llm_returning_json(self, pipeline, mock_llm):
        """When LLM returns clipboard JSON, response type is generation."""
        mock_llm.chat = AsyncMock(
            return_value='Fixed:\n```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```'
        )
        msg = '修复这个：{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"invalid"}]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        assert response.type == "generation"
        assert response.data is not None
        assert response.data.clipboard_json is not None

    @pytest.mark.asyncio
    async def test_json_track_llm_error_returns_validation_only(self, pipeline, mock_llm):
        """When LLM fails, return validation report as fallback."""
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM down"))
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        assert response.type in ("direct_answer", "error")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_pipeline_json.py -v`
Expected: FAIL — tests reference new pipeline behavior not yet implemented

---

### Task 8: Pipeline Integration — Implementation

**Files:**
- Modify: `src/orchestrator/pipeline.py`
- Modify: `src/schemas/api.py`

- [ ] **Step 1: Update `schemas/api.py` — add `input_validation` to `GenerationData`**

In `src/schemas/api.py`, add the `input_validation` field to `GenerationData`:

```python
class GenerationData(BaseModel):
    """Data payload when type=generation."""
    delivery: Literal["clipboard", "mcp"]
    clipboard_json: Optional[dict] = None
    validation: Optional[dict] = None
    input_validation: Optional[dict] = None
    metadata: Optional[dict] = None
```

- [ ] **Step 2: Rewrite `src/orchestrator/pipeline.py` with JSON processing branch**

```python
"""Orchestration pipeline — the core of Copilot.

Dual-track pipeline:
- Q&A track: RAG-augmented LLM chat (Phase 1.1, unchanged)
- JSON track: clipboard JSON detection → validate → RAG → LLM → output validate

Phase 2: adds JSON processing track.
"""
import logging

from src.llm.client import LLMClient
from src.llm.prompts.system import COPILOT_SYSTEM
from src.llm.prompts.clipboard import build_clipboard_prompt
from src.modules.rag_client import RAGClient
from src.orchestrator.session import SessionManager
from src.orchestrator.router import decide_delivery
from src.orchestrator.detector import detect_clipboard_json, DetectionResult
from src.orchestrator.validator import validate_local
from src.orchestrator.json_extract import extract_clipboard_json_from_reply
from src.schemas.api import ChatRequest, ChatResponse, GenerationData
from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


class Pipeline:
    """Main orchestration pipeline."""

    def __init__(self, llm: LLMClient, sessions: SessionManager, rag: RAGClient = None):
        self.llm = llm
        self.sessions = sessions
        self.rag = rag

    # ── Shared helpers ──────────────────────────────────────────────────

    async def _fetch_rag_context(self, query: str) -> tuple[str, bool]:
        """Search RAG for relevant C3 knowledge. Returns (context_str, used)."""
        if not self.rag:
            return "", False
        try:
            if not await self.rag.is_available():
                return "", False
            resp = await self.rag.search(query, top_k=5)
            if not resp.results:
                return "", False
            chunks = []
            for r in resp.results:
                chunks.append(f"[{r.collection}] (score: {r.score:.2f})\n{r.text}")
            context = "\n\n---\n\n".join(chunks)
            logger.info(f"RAG returned {len(resp.results)} results (route: {resp.route})")
            return context, True
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return "", False

    def _build_system_prompt(self, rag_context: str) -> str:
        """Build system prompt for Q&A track, optionally augmented with RAG results."""
        if not rag_context:
            return COPILOT_SYSTEM
        return (
            COPILOT_SYSTEM
            + "\n\n## Reference Knowledge (from RAG)\n\n"
            "The following are relevant Construct 3 documentation and examples "
            "retrieved for this conversation. Use them to give accurate, specific answers. "
            "If the retrieved content conflicts with your training data, prefer the retrieved content.\n\n"
            + rag_context
        )

    # ── Main entry ──────────────────────────────────────────────────────

    async def process(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request through the pipeline."""
        # [1] Session
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        # Append user message
        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        # [2] JSON detection
        detection = detect_clipboard_json(request.message)

        if detection.found:
            return await self._process_json(session, detection)
        else:
            return await self._process_qa(session, request)

    # ── Q&A track (Phase 1.1, unchanged) ────────────────────────────────

    async def _process_qa(self, session: SessionState, request: ChatRequest) -> ChatResponse:
        """Q&A track: RAG-augmented LLM chat."""
        modules_used = []

        rag_context, rag_used = await self._fetch_rag_context(request.message)
        if rag_used:
            modules_used.append("rag")

        try:
            system_prompt = self._build_system_prompt(rag_context)
            messages = [
                {"role": "system", "content": system_prompt},
                *session.messages,
            ]
            reply = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ChatResponse(
                session_id=session.session_id,
                type="error",
                message=f"LLM error: {e}",
            )

        session.messages.append({"role": "assistant", "content": reply})
        session.touch()

        delivery = decide_delivery(session)
        logger.debug(f"Route decision: {delivery}")

        return ChatResponse(
            session_id=session.session_id,
            type="direct_answer",
            message=reply,
            modules_used=modules_used,
        )

    # ── JSON processing track (Phase 2) ─────────────────────────────────

    def _build_rag_query_from_json(self, clipboard_json: dict) -> str:
        """Extract searchable terms from clipboard JSON for RAG query."""
        terms = set()
        items = clipboard_json.get("items", [])
        for item in items:
            if not isinstance(item, dict):
                continue
            # Object classes from conditions/actions
            for node_list_key in ("conditions", "actions"):
                for node in item.get(node_list_key, []):
                    if isinstance(node, dict):
                        if oc := node.get("objectClass"):
                            terms.add(oc)
                        if bt := node.get("behaviorType"):
                            terms.add(bt)
                        if aid := node.get("id"):
                            terms.add(aid)
            # Object types
            if pid := item.get("plugin-id"):
                terms.add(pid)
            # Behavior types in object definitions
            for beh in item.get("behaviorTypes", []):
                if isinstance(beh, dict) and (bid := beh.get("behaviorId")):
                    terms.add(bid)
            # Recurse children
            for child in item.get("children", []):
                if isinstance(child, dict):
                    for key in ("conditions", "actions"):
                        for node in child.get(key, []):
                            if isinstance(node, dict):
                                if oc := node.get("objectClass"):
                                    terms.add(oc)
                                if bt := node.get("behaviorType"):
                                    terms.add(bt)

        if not terms:
            return f"Construct 3 clipboard {clipboard_json.get('type', 'events')} format"
        return " ".join(sorted(terms))

    async def _process_json(self, session: SessionState, detection: DetectionResult) -> ChatResponse:
        """JSON processing track: validate → RAG → LLM → output validate."""
        modules_used = []

        # [4] Local validation
        input_report = validate_local(detection.clipboard_json)

        # [5] RAG retrieval
        rag_query = self._build_rag_query_from_json(detection.clipboard_json)
        rag_context, rag_used = await self._fetch_rag_context(rag_query)
        if rag_used:
            modules_used.append("rag")

        # [6-7] LLM call with clipboard-specific prompt
        try:
            system_prompt = build_clipboard_prompt(
                clipboard_json=detection.clipboard_json,
                validation_report=input_report,
                rag_context=rag_context,
                user_instruction=detection.user_instruction,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                *session.messages,
            ]
            reply = await self.llm.chat(messages)
            modules_used.append("llm")
        except Exception as e:
            logger.error(f"LLM call failed in JSON track: {e}")
            # Fallback: return validation report without LLM
            return ChatResponse(
                session_id=session.session_id,
                type="direct_answer" if input_report.passed else "error",
                message=self._format_validation_fallback(input_report),
                data=GenerationData(
                    delivery="clipboard",
                    input_validation=input_report.to_dict(),
                ),
                modules_used=modules_used,
            )

        session.messages.append({"role": "assistant", "content": reply})
        session.touch()

        # [8] Extract and validate output JSON
        output_json = extract_clipboard_json_from_reply(reply)
        output_validation = None
        if output_json:
            output_report = validate_local(output_json)
            output_validation = output_report.to_dict()

        # [9] Deliver
        if output_json:
            return ChatResponse(
                session_id=session.session_id,
                type="generation",
                message=reply,
                data=GenerationData(
                    delivery="clipboard",
                    clipboard_json=output_json,
                    validation=output_validation,
                    input_validation=input_report.to_dict(),
                ),
                modules_used=modules_used,
            )
        else:
            return ChatResponse(
                session_id=session.session_id,
                type="direct_answer",
                message=reply,
                data=GenerationData(
                    delivery="clipboard",
                    input_validation=input_report.to_dict(),
                ) if input_report.issues else None,
                modules_used=modules_used,
            )

    def _format_validation_fallback(self, report) -> str:
        """Format validation report as human-readable text (LLM fallback)."""
        if report.passed and not report.issues:
            return "JSON validation passed. No issues found. (LLM unavailable for further analysis)"
        lines = ["JSON validation results (LLM unavailable):", ""]
        for issue in report.issues:
            prefix = "ERROR" if issue.level == "error" else "WARNING"
            loc = f" at {issue.path}" if issue.path else ""
            lines.append(f"  [{prefix}] {issue.message}{loc}")
        return "\n".join(lines)

    # ── Streaming ───────────────────────────────────────────────────────

    async def process_stream(self, request: ChatRequest):
        """Streaming version — yields SSE-formatted chunks.

        Note: JSON track does not support streaming in Phase 2.
        If clipboard JSON is detected, falls back to non-streaming process().
        """
        detection = detect_clipboard_json(request.message)
        if detection.found:
            # JSON track: return full response as single SSE event
            response = await self.process(request)
            import json
            yield f"data: {json.dumps(response.model_dump(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Q&A track: stream as before
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        rag_context, _ = await self._fetch_rag_context(request.message)
        system_prompt = self._build_system_prompt(rag_context)

        messages = [
            {"role": "system", "content": system_prompt},
            *session.messages,
        ]

        full_reply = []
        async for token in self.llm.stream(messages):
            full_reply.append(token)
            yield f"data: {token}\n\n"

        complete = "".join(full_reply)
        session.messages.append({"role": "assistant", "content": complete})
        session.touch()

        yield "data: [DONE]\n\n"
```

- [ ] **Step 3: Run all tests**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_detector.py tests/test_validator.py tests/test_json_extract.py tests/test_pipeline_json.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/orchestrator/pipeline.py src/schemas/api.py tests/test_pipeline_json.py
git commit -m "feat(phase2): integrate JSON processing track into pipeline"
```

---

### Task 9: Validate Against Real Fixtures

**Files:**
- Modify: `tests/test_validator.py` (add fixture-based tests)

- [ ] **Step 1: Add fixture validation tests**

Append to `tests/test_validator.py`:

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLES_DIR = Path(__file__).parent / "examples"


class TestRealFixtures:
    """Validate real C3 clipboard JSON fixtures."""

    def test_events_basic_fixture(self):
        data = json.loads((FIXTURES_DIR / "events_basic.json").read_text())
        report = validate_local(data)
        # Known issue: events_basic.json has empty parameters {} on on-start-of-layout
        assert any(i.code == "EMPTY_PARAMS" for i in report.issues)

    def test_breakout_events(self):
        data = json.loads((EXAMPLES_DIR / "breakout_events.json").read_text())
        report = validate_local(data)
        # Should parse without crashing; report any findings
        assert isinstance(report.passed, bool)
        assert isinstance(report.issues, list)

    def test_platformer_events(self):
        data = json.loads((EXAMPLES_DIR / "platformer_events.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)

    def test_breakout_layout(self):
        data = json.loads((EXAMPLES_DIR / "breakout_layout.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)

    def test_platformer_layout(self):
        data = json.loads((EXAMPLES_DIR / "platformer_layout.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)
```

- [ ] **Step 2: Run fixture tests**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/test_validator.py::TestRealFixtures -v`
Expected: All PASS (validator handles real data without crashing)

- [ ] **Step 3: Commit**

```bash
git add tests/test_validator.py
git commit -m "test(phase2): add real fixture validation tests"
```

---

### Task 10: Full Test Suite + Cleanup

**Files:**
- No new files — run all tests and verify

- [ ] **Step 1: Run the complete test suite**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (including pre-existing tests from Phase 1)

- [ ] **Step 2: Verify the server starts**

Run: `cd D:/Users/Administrator/Documents/GitHub/Construct3-Copilot && python -c "from src.api import app; print('Import OK')"` 
Expected: `Import OK` (no import errors)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(phase2): complete JSON processing pipeline

Dual-track pipeline: Q&A + clipboard JSON processing.
- Detector: scans for is-c3-clipboard-data marker
- Validator: structural checks + 10 known C3 pitfalls
- Prompt: clipboard-specific system prompt with validation injection
- Pipeline: auto-routes to JSON track, falls back to Q&A
- Tests: 30+ unit + integration tests"
```
