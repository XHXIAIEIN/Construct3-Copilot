"""Tests for the local pre-validation script."""
import json
import subprocess
import sys

SCRIPT = ".claude/plugins/construct3-copilot/scripts/generate/prevalidate.py"


def run_prevalidate(json_str: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, SCRIPT, json_str],
        capture_output=True, text=True,
        cwd="D:/Users/Administrator/Documents/GitHub/Construct3-Copilot",
    )
    return result.returncode, result.stdout.strip()


def test_valid_json_passes():
    data = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [],
    })
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    assert code == 0
    assert parsed["passed"] is True


def test_missing_flag_fails():
    data = json.dumps({"type": "events", "items": []})
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    assert code == 1
    assert parsed["passed"] is False
    assert len(parsed["errors"]) > 0


def test_bad_type_fails():
    data = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "nonsense",
        "items": [],
    })
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    assert code == 1
    assert parsed["passed"] is False


def test_invalid_json_fails():
    code, output = run_prevalidate("{not valid json")
    parsed = json.loads(output)
    assert code == 1
    assert "error" in parsed


def test_invalid_event_type():
    data = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [{"eventType": "bogus"}],
    })
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    assert code == 1
    assert parsed["passed"] is False


def test_missing_ace_fields():
    data = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [{
            "eventType": "block",
            "conditions": [{"type": "sprite"}],
            "actions": [{"id": "set-pos"}],
        }],
    })
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    assert code == 1
    assert any("missing 'id'" in e for e in parsed["errors"])
    assert any("missing 'type'" in e for e in parsed["errors"])


def test_variable_missing_comment_warning():
    data = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [{"eventType": "variable", "name": "score", "type": "number"}],
    })
    code, output = run_prevalidate(data)
    parsed = json.loads(output)
    # Should pass (warning, not error) but have warnings
    assert code == 0
    assert parsed["passed"] is True
    assert len(parsed["warnings"]) > 0
    assert any("comment" in w for w in parsed["warnings"])
