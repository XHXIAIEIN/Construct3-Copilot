"""Clipboard JSON validator for Construct 3 clipboard data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CLIPBOARD_TYPES = {
    "events",
    "object-types",
    "layouts",
    "world-instances",
    "event-sheets",
}

VALID_EVENT_TYPES = {
    "block",
    "variable",
    "comment",
    "group",
    "function-block",
}

# V1 behaviour IDs (capitalised) → V2 equivalents (lowercase)
V1_TO_V2_BEHAVIORS: dict[str, str] = {
    "Solid": "solid",
    "ScrollTo": "scrollto",
}

# Behaviours that no longer exist in V2
REMOVED_BEHAVIORS: set[str] = {"DestroyOutsideLayout"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    level: str          # "error" | "warning" | "info"
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: str = ""

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.level == "error":
            self.passed = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "issues": [
                {
                    "level": i.level,
                    "code": i.code,
                    "message": i.message,
                    "path": i.path,
                }
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# Layer 1 — Structural validation
# ---------------------------------------------------------------------------


def _check_structural(data: dict, report: ValidationReport) -> None:
    # 1. Clipboard marker
    if not data.get("is-c3-clipboard-data"):
        report.add(ValidationIssue(
            level="error",
            code="MISSING_CLIPBOARD_MARKER",
            message="Missing required field 'is-c3-clipboard-data: true'.",
            path="is-c3-clipboard-data",
        ))

    # 2. type enum
    clip_type = data.get("type")
    if clip_type not in VALID_CLIPBOARD_TYPES:
        report.add(ValidationIssue(
            level="error",
            code="INVALID_TYPE",
            message=(
                f"Invalid clipboard type '{clip_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_CLIPBOARD_TYPES))}."
            ),
            path="type",
        ))

    # 3. items array
    items = data.get("items")
    if items is None:
        report.add(ValidationIssue(
            level="error",
            code="MISSING_ITEMS",
            message="Missing required field 'items'.",
            path="items",
        ))
        return  # nothing left to validate without items

    if not isinstance(items, list):
        report.add(ValidationIssue(
            level="error",
            code="ITEMS_NOT_ARRAY",
            message="'items' must be an array.",
            path="items",
        ))
        return

    # 4. eventType enum (only for events clipboard)
    if clip_type == "events":
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            et = item.get("eventType")
            if et not in VALID_EVENT_TYPES:
                report.add(ValidationIssue(
                    level="error",
                    code="INVALID_EVENT_TYPE",
                    message=(
                        f"Item[{idx}] has unknown eventType '{et}'. "
                        f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}."
                    ),
                    path=f"items[{idx}].eventType",
                ))


# ---------------------------------------------------------------------------
# Layer 2 — Known pitfalls
# ---------------------------------------------------------------------------


def _iter_conditions_recursive(items: list, *, is_children: bool = False):
    """Yield (condition_dict, path, is_children) tuples recursively."""
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if item.get("eventType") == "block":
            conditions = item.get("conditions", [])
            if isinstance(conditions, list):
                for c in conditions:
                    yield c, is_children
            children = item.get("children", [])
            if isinstance(children, list):
                yield from _iter_conditions_recursive(children, is_children=True)


def _iter_all_conditions_actions(items: list):
    """Yield all condition/action dicts in any block recursively."""
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("eventType") == "block":
            for c in item.get("conditions", []) or []:
                if isinstance(c, dict):
                    yield c
            for a in item.get("actions", []) or []:
                if isinstance(a, dict):
                    yield a
            for child in item.get("children", []) or []:
                yield from _iter_all_conditions_actions([child])


def _check_pitfalls(data: dict, report: ValidationReport) -> None:
    clip_type = data.get("type")
    items = data.get("items")
    if not isinstance(items, list):
        return

    if clip_type == "events":
        _check_event_pitfalls(items, report)

    if clip_type == "object-types":
        _check_object_type_pitfalls(items, report)


def _check_event_pitfalls(items: list, report: ValidationReport) -> None:
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        et = item.get("eventType")

        # --- variable missing comment ---
        if et == "variable" and "comment" not in item:
            report.add(ValidationIssue(
                level="warning",
                code="VARIABLE_MISSING_COMMENT",
                message=f"Variable '{item.get('name', '?')}' is missing the 'comment' field.",
                path=f"items[{idx}]",
            ))

        # --- block-level checks ---
        if et == "block":
            conditions = item.get("conditions") or []
            if isinstance(conditions, list):
                # empty parameters {}
                for cidx, cond in enumerate(conditions):
                    if isinstance(cond, dict) and cond.get("parameters") == {}:
                        report.add(ValidationIssue(
                            level="warning",
                            code="EMPTY_PARAMS",
                            message=(
                                f"Condition[{cidx}] in block[{idx}] has empty 'parameters' object. "
                                "Omit the field entirely instead."
                            ),
                            path=f"items[{idx}].conditions[{cidx}].parameters",
                        ))

                # multiple triggers in one block
                trigger_ids = [
                    c.get("id", "") for c in conditions
                    if isinstance(c, dict) and str(c.get("id", "")).startswith("on-")
                ]
                if len(trigger_ids) > 1:
                    report.add(ValidationIssue(
                        level="error",
                        code="MULTIPLE_TRIGGERS",
                        message=(
                            f"Block[{idx}] has {len(trigger_ids)} trigger conditions "
                            f"({', '.join(trigger_ids)}). A block may have at most one trigger."
                        ),
                        path=f"items[{idx}].conditions",
                    ))

            # trigger in children
            children = item.get("children") or []
            if isinstance(children, list):
                for cidx, child in enumerate(children):
                    if not isinstance(child, dict):
                        continue
                    child_conds = child.get("conditions") or []
                    for ccidx, cc in enumerate(child_conds):
                        if isinstance(cc, dict) and str(cc.get("id", "")).startswith("on-"):
                            report.add(ValidationIssue(
                                level="error",
                                code="TRIGGER_IN_CHILDREN",
                                message=(
                                    f"Sub-event block[{idx}].children[{cidx}] contains trigger "
                                    f"condition '{cc.get('id')}'. Triggers cannot be in sub-events."
                                ),
                                path=f"items[{idx}].children[{cidx}].conditions[{ccidx}]",
                            ))


def _check_object_type_pitfalls(items: list, report: ValidationReport) -> None:
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        # effectTypes must be array
        effect_types = item.get("effectTypes")
        if effect_types is not None and not isinstance(effect_types, list):
            report.add(ValidationIssue(
                level="error",
                code="EFFECT_TYPES_NOT_ARRAY",
                message=(
                    f"Object '{item.get('name', '?')}' effectTypes must be an array, not an object."
                ),
                path=f"items[{idx}].effectTypes",
            ))

        # instanceVariables must be array
        inst_vars = item.get("instanceVariables")
        if inst_vars is not None and not isinstance(inst_vars, list):
            report.add(ValidationIssue(
                level="error",
                code="INSTANCE_VARS_NOT_ARRAY",
                message=(
                    f"Object '{item.get('name', '?')}' instanceVariables must be an array, not an object."
                ),
                path=f"items[{idx}].instanceVariables",
            ))

        # behaviour checks
        behavior_types = item.get("behaviorTypes") or []
        if isinstance(behavior_types, list):
            for bidx, btype in enumerate(behavior_types):
                if not isinstance(btype, dict):
                    continue
                bid = btype.get("behaviorId", "")

                if bid in V1_TO_V2_BEHAVIORS:
                    report.add(ValidationIssue(
                        level="warning",
                        code="DEPRECATED_BEHAVIOR_V1",
                        message=(
                            f"behaviorId '{bid}' is a V1 capitalised ID. "
                            f"Use '{V1_TO_V2_BEHAVIORS[bid]}' instead."
                        ),
                        path=f"items[{idx}].behaviorTypes[{bidx}].behaviorId",
                    ))

                if bid in REMOVED_BEHAVIORS:
                    report.add(ValidationIssue(
                        level="error",
                        code="DEPRECATED_BEHAVIOR_REMOVED",
                        message=(
                            f"behaviorId '{bid}' has been removed in Construct 3 V2 "
                            "and is no longer available."
                        ),
                        path=f"items[{idx}].behaviorTypes[{bidx}].behaviorId",
                    ))


# ---------------------------------------------------------------------------
# Layer 3 — SID uniqueness
# ---------------------------------------------------------------------------


def _collect_sids(obj: Any, sids: list[int]) -> None:
    """Recursively collect all 'sid' integer values from a JSON structure."""
    if isinstance(obj, dict):
        if "sid" in obj:
            val = obj["sid"]
            if isinstance(val, int):
                sids.append(val)
        for v in obj.values():
            _collect_sids(v, sids)
    elif isinstance(obj, list):
        for item in obj:
            _collect_sids(item, sids)


def _check_sid_uniqueness(data: dict, report: ValidationReport) -> None:
    sids: list[int] = []
    _collect_sids(data, sids)

    seen: set[int] = set()
    duplicates: set[int] = set()
    for sid in sids:
        if sid in seen:
            duplicates.add(sid)
        seen.add(sid)

    for sid in sorted(duplicates):
        report.add(ValidationIssue(
            level="error",
            code="DUPLICATE_SID",
            message=f"SID {sid} appears more than once. All SIDs must be unique.",
            path="(multiple locations)",
        ))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_local(data: dict) -> ValidationReport:
    """Run all validation layers and return a ValidationReport."""
    report = ValidationReport()

    _check_structural(data, report)
    _check_pitfalls(data, report)
    _check_sid_uniqueness(data, report)

    errors = sum(1 for i in report.issues if i.level == "error")
    warnings = sum(1 for i in report.issues if i.level == "warning")
    report.summary = f"{errors} error(s), {warnings} warning(s)"

    return report
