#!/usr/bin/env python3
"""
Simulate real user journeys for the construct3-copilot skill and write reports.

Outputs:
  - tests/regressions/skill_user_simulation_report.md
  - tests/regressions/skill_user_simulation_report.json
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "construct3-copilot"
REPORT_DIR = ROOT / "tests" / "regressions"
REPORT_MD = REPORT_DIR / "skill_user_simulation_report.md"
REPORT_JSON = REPORT_DIR / "skill_user_simulation_report.json"


def load_validator():
    validator_path = SKILL_DIR / "scripts" / "validate_output.py"
    spec = importlib.util.spec_from_file_location("validate_output", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validator: {validator_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.C3ClipboardValidator


def run_cmd(args: list[str]) -> dict:
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def validate_file(validator_cls, path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    v = validator_cls()
    ok = v.validate(data)
    return {
        "file": str(path.relative_to(ROOT)),
        "ok": ok,
        "errors": v.errors,
        "warnings": v.warnings,
    }


def validate_payload(validator_cls, payload: dict) -> dict:
    v = validator_cls()
    ok = v.validate(payload)
    return {"ok": ok, "errors": v.errors, "warnings": v.warnings}


def evaluate_quality_gate(scenario: dict) -> dict:
    reasons: list[str] = []
    schema_checks = scenario.get("schema_checks", [])
    output_validation = scenario.get("output_validation", [])
    preflight = scenario.get("preflight")
    invalid_attempt_validation = scenario.get("invalid_attempt_validation")
    fixed_attempt_validation = scenario.get("fixed_attempt_validation")

    if schema_checks:
        bad_schema = [c for c in schema_checks if c.get("returncode", 1) != 0]
        if bad_schema:
            reasons.append(f"{len(bad_schema)} schema check(s) failed")

    if output_validation:
        bad_outputs = [v for v in output_validation if not v.get("ok", False)]
        if bad_outputs:
            reasons.append(f"{len(bad_outputs)} output validation(s) failed")

    if preflight and preflight.get("returncode", 1) != 0:
        reasons.append("preflight failed")

    if invalid_attempt_validation is not None and invalid_attempt_validation.get("ok", True):
        reasons.append("invalid attempt unexpectedly passed")
    if fixed_attempt_validation is not None and not fixed_attempt_validation.get("ok", False):
        reasons.append("fixed attempt failed validation")

    return {"passed": len(reasons) == 0, "reasons": reasons}


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    validator_cls = load_validator()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scenarios: list[dict] = []

    # Scenario 1: complete game request.
    s1_prompt = "做一个打砖块游戏，包含计分和生命值，给我可粘贴 JSON。"
    s1 = {
        "id": "S1",
        "name": "Complete Game Generation",
        "user_prompt": s1_prompt,
        "intent_ir": {
            "gameplay": ["breakout loop", "score", "lives"],
            "ui": ["score text"],
            "assets": ["Paddle", "Ball", "Brick", "ScoreText", "Mouse"],
            "open_questions": [],
            "assumptions": ["single-level prototype"],
        },
        "schema_checks": [
            run_cmd(["python", str(SKILL_DIR / "scripts" / "query_schema.py"), "search", "collision"]),
            run_cmd(["python", str(SKILL_DIR / "scripts" / "query_schema.py"), "plugin", "system", "add-to-eventvar"]),
        ],
        "output_validation": [
            validate_file(validator_cls, ROOT / "tests" / "examples" / "breakout_layout.json"),
            validate_file(validator_cls, ROOT / "tests" / "examples" / "breakout_events.json"),
        ],
        "preflight": run_cmd(["python", "scripts/preflight.py", "tests/examples/breakout_events.json"]),
    }
    s1["quality_gate"] = evaluate_quality_gate(s1)
    scenarios.append(s1)

    # Scenario 2: incremental feature request.
    s2_prompt = "在现有项目里加 WASD 8 方向移动，保持事件表可直接粘贴。"
    s2 = {
        "id": "S2",
        "name": "Incremental Feature Update",
        "user_prompt": s2_prompt,
        "intent_ir": {
            "gameplay": ["WASD movement"],
            "ui": [],
            "assets": ["Player", "Keyboard"],
            "open_questions": [],
            "assumptions": ["Player has 8Direction behavior"],
        },
        "schema_checks": [
            run_cmd(["python", str(SKILL_DIR / "scripts" / "query_schema.py"), "behavior", "8direction", "simulate-control"]),
            run_cmd(["python", str(SKILL_DIR / "scripts" / "query_schema.py"), "plugin", "keyboard", "key-is-down"]),
        ],
        "output_validation": [validate_file(validator_cls, ROOT / "tests" / "fixtures" / "events_basic.json")],
        "preflight": run_cmd(["python", "scripts/preflight.py", "tests/fixtures/events_basic.json"]),
    }
    s2["quality_gate"] = evaluate_quality_gate(s2)
    scenarios.append(s2)

    # Scenario 3: out-of-scope/error recovery.
    s3_prompt = "加暂停功能（以前示例写了 toggle-boolean）。"
    bad_payload = {
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [
            {"eventType": "variable", "name": "IsPaused", "type": "boolean", "initialValue": "false", "comment": ""},
            {
                "eventType": "block",
                "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 27}}],
                "actions": [{"id": "toggle-boolean", "objectClass": "System", "parameters": {"variable": "IsPaused"}}],
            },
        ],
    }
    fixed_payload = {
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [
            {"eventType": "variable", "name": "IsPaused", "type": "boolean", "initialValue": "false", "comment": ""},
            {
                "eventType": "block",
                "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 27}}],
                "actions": [{"id": "toggle-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused"}}],
            },
        ],
    }
    bad_check = validate_payload(validator_cls, bad_payload)
    similar = run_cmd(["python", "scripts/find_similar_failures.py", "unknown action id toggle-boolean", "--top", "1"])
    fixed_check = validate_payload(validator_cls, fixed_payload)
    s3 = {
        "id": "S3",
        "name": "Out-of-Scope/Error Recovery",
        "user_prompt": s3_prompt,
        "intent_ir": {
            "gameplay": ["pause toggle"],
            "ui": [],
            "assets": ["Keyboard"],
            "open_questions": [],
            "assumptions": [],
        },
        "invalid_attempt_validation": bad_check,
        "similar_case_lookup": similar,
        "fixed_attempt_validation": fixed_check,
    }
    s3["quality_gate"] = evaluate_quality_gate(s3)
    scenarios.append(s3)

    summary = {
        "run_at": now,
        "scenarios_total": len(scenarios),
        "scenarios_passed": sum(1 for s in scenarios if s.get("quality_gate", {}).get("passed", False)),
        "notes": [
            "Quality gate requires schema checks, clipboard validation, and preflight to pass.",
            "This simulation measures workflow reliability from user pasteability perspective.",
        ],
    }

    payload = {"summary": summary, "scenarios": scenarios}
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# Skill User Simulation Report")
    md.append("")
    md.append(f"- Run at: `{now}`")
    md.append(f"- Total scenarios: `{summary['scenarios_total']}`")
    md.append(f"- Passed scenarios: `{summary['scenarios_passed']}`")
    md.append("")
    for s in scenarios:
        md.append(f"## {s['id']} - {s['name']}")
        md.append(f"- User prompt: `{s['user_prompt']}`")
        md.append(f"- Intent IR: `{json.dumps(s['intent_ir'], ensure_ascii=False)}`")
        if "schema_checks" in s:
            md.append("- Schema checks:")
            for c in s["schema_checks"]:
                md.append(f"  - `{c['command']}` -> rc={c['returncode']}")
        if "output_validation" in s:
            md.append("- Output validation:")
            for v in s["output_validation"]:
                md.append(f"  - `{v['file']}` -> ok={v['ok']}, errors={len(v['errors'])}, warnings={len(v['warnings'])}")
        if "preflight" in s:
            md.append(f"- Preflight: rc={s['preflight']['returncode']}")
        if "invalid_attempt_validation" in s:
            md.append(
                "- Invalid attempt: "
                f"ok={s['invalid_attempt_validation']['ok']}, errors={len(s['invalid_attempt_validation']['errors'])}"
            )
            md.append(f"- Similar-case lookup rc={s['similar_case_lookup']['returncode']}")
            md.append(
                "- Fixed attempt: "
                f"ok={s['fixed_attempt_validation']['ok']}, errors={len(s['fixed_attempt_validation']['errors'])}"
            )
        qg = s.get("quality_gate", {})
        md.append(f"- Quality gate: passed={qg.get('passed', False)}")
        for reason in qg.get("reasons", []):
            md.append(f"  - reason: {reason}")
        md.append("")

    md.append("## Artifacts")
    md.append(f"- JSON report: `{REPORT_JSON.relative_to(ROOT)}`")
    md.append(f"- This markdown: `{REPORT_MD.relative_to(ROOT)}`")
    md.append("")
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"Wrote: {REPORT_MD}")
    print(f"Wrote: {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
