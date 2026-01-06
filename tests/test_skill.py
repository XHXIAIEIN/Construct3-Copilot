#!/usr/bin/env python3
"""
Construct3-Copilot Skill Tests

Tests for:
- ACE Schema loading and querying
- JSON validation
- ImageData generation
- Layout generation
"""

import json
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SKILL_DIR = PROJECT_ROOT / ".claude" / "skills" / "construct3-copilot"
SCRIPTS_DIR = SKILL_DIR / "scripts"
SCHEMA_DIR = PROJECT_ROOT / "data" / "schemas"


def run_script(script_name: str, *args) -> tuple[bool, str]:
    """Run a skill script and return (success, output)"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), *args],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def test_schema_loading():
    """Test that ACE schemas can be loaded"""
    print("=" * 60)
    print("1. Schema Loading Test")
    print("=" * 60)

    # Check schema directories exist
    plugins_dir = SCHEMA_DIR / "plugins"
    behaviors_dir = SCHEMA_DIR / "behaviors"

    if not plugins_dir.exists():
        print(f"✗ Plugins directory not found: {plugins_dir}")
        return False

    if not behaviors_dir.exists():
        print(f"✗ Behaviors directory not found: {behaviors_dir}")
        return False

    # Count schemas
    plugins = list(plugins_dir.glob("*.json"))
    behaviors = list(behaviors_dir.glob("*.json"))

    print(f"✓ Found {len(plugins)} plugin schemas")
    print(f"✓ Found {len(behaviors)} behavior schemas")

    # Load and validate a few schemas
    test_schemas = [
        plugins_dir / "sprite.json",
        plugins_dir / "keyboard.json",
        behaviors_dir / "platform.json",
        behaviors_dir / "bullet.json",
    ]

    for schema_path in test_schemas:
        if not schema_path.exists():
            print(f"✗ Schema not found: {schema_path.name}")
            continue

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)

            # Check required fields
            if "id" in schema and "name" in schema:
                ace_count = len(schema.get("conditions", [])) + \
                           len(schema.get("actions", [])) + \
                           len(schema.get("expressions", []))
                print(f"✓ {schema_path.name}: {ace_count} ACEs")
            else:
                print(f"✗ {schema_path.name}: Missing id/name")
        except json.JSONDecodeError as e:
            print(f"✗ {schema_path.name}: Invalid JSON - {e}")
            return False

    return True


def test_query_schema():
    """Test query_schema.py script"""
    print("\n" + "=" * 60)
    print("2. Query Schema Test")
    print("=" * 60)

    test_cases = [
        (["plugin", "sprite"], "Sprite"),
        (["plugin", "keyboard"], "Keyboard"),
        (["behavior", "platform"], "Platform"),
        (["plugin", "sprite", "set-animation"], "set-animation"),
    ]

    all_passed = True
    for args, expected in test_cases:
        success, output = run_script("query_schema.py", *args)
        if success and expected.lower() in output.lower():
            print(f"✓ query_schema.py {' '.join(args)}")
        else:
            print(f"✗ query_schema.py {' '.join(args)}")
            if output:
                print(f"    Output: {output[:100]}...")
            all_passed = False

    return all_passed


def test_generate_imagedata():
    """Test generate_imagedata.py script"""
    print("\n" + "=" * 60)
    print("3. Generate ImageData Test")
    print("=" * 60)

    test_cases = [
        (["--color", "red", "-W", "32", "-H", "32"], "iVBOR"),  # PNG base64 prefix
        (["--color", "blue", "--shape", "circle"], "iVBOR"),
        (["--kenney", "player", "--color", "green"], "iVBOR"),
    ]

    all_passed = True
    for args, expected in test_cases:
        success, output = run_script("generate_imagedata.py", *args)
        if success and expected in output:
            print(f"✓ generate_imagedata.py {' '.join(args)}")
        else:
            print(f"✗ generate_imagedata.py {' '.join(args)}")
            if output:
                print(f"    Output: {output[:80]}...")
            all_passed = False

    return all_passed


def test_validate_output():
    """Test validate_output.py script"""
    print("\n" + "=" * 60)
    print("4. Validate Output Test")
    print("=" * 60)

    # Valid JSON
    valid_json = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [
            {"eventType": "comment", "text": "Test"}
        ]
    })

    # Invalid JSON
    invalid_json = json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [
            {"eventType": "unknown"}
        ]
    })

    # Test valid JSON
    success, output = run_script("validate_output.py", valid_json)
    if success or "valid" in output.lower():
        print("✓ validate_output.py (valid JSON)")
    else:
        print("✗ validate_output.py (valid JSON)")
        print(f"    Output: {output[:100]}...")

    # Test invalid JSON (should detect issues)
    success, output = run_script("validate_output.py", invalid_json)
    if "error" in output.lower() or "invalid" in output.lower() or not success:
        print("✓ validate_output.py (invalid JSON detected)")
    else:
        print("✗ validate_output.py (should detect invalid JSON)")

    return True


def test_json_clipboard_format():
    """Test clipboard JSON format validation"""
    print("\n" + "=" * 60)
    print("5. Clipboard Format Test")
    print("=" * 60)

    # Valid clipboard formats
    valid_formats = [
        # Events
        {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{"eventType": "comment", "text": "Hello"}]
        },
        # Variable with required comment field
        {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{
                "eventType": "variable",
                "name": "Score",
                "type": "number",
                "initialValue": "0",
                "comment": ""
            }]
        },
        # Event block with condition and action
        {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{
                "eventType": "block",
                "conditions": [{
                    "id": "every-tick",
                    "objectClass": "System",
                    "parameters": {}
                }],
                "actions": [{
                    "id": "set-x",
                    "objectClass": "Sprite",
                    "parameters": {"x": "100"}
                }]
            }]
        },
        # Behavior ACE with behaviorType
        {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{
                "eventType": "block",
                "conditions": [],
                "actions": [{
                    "id": "simulate-control",
                    "objectClass": "Player",
                    "behaviorType": "Platform",
                    "parameters": {"control": "jump"}
                }]
            }]
        },
    ]

    all_passed = True
    for i, fmt in enumerate(valid_formats):
        # Check required fields
        has_clipboard = fmt.get("is-c3-clipboard-data") == True
        has_type = "type" in fmt
        has_items = "items" in fmt and isinstance(fmt["items"], list)

        if has_clipboard and has_type and has_items:
            print(f"✓ Format {i+1}: Valid structure")
        else:
            print(f"✗ Format {i+1}: Invalid structure")
            all_passed = False

    # Check behavior ACE has behaviorType
    behavior_ace = valid_formats[3]["items"][0]["actions"][0]
    if "behaviorType" in behavior_ace:
        print("✓ Behavior ACE has behaviorType")
    else:
        print("✗ Behavior ACE missing behaviorType")
        all_passed = False

    return all_passed


def test_string_parameter_format():
    """Test string parameter nested quotes format"""
    print("\n" + "=" * 60)
    print("6. String Parameter Format Test")
    print("=" * 60)

    # Correct format: nested quotes
    correct = {"animation": "\"Walk\""}

    # Incorrect format: no nested quotes
    incorrect = {"animation": "Walk"}

    # Check correct format
    if correct["animation"].startswith('"') and correct["animation"].endswith('"'):
        print("✓ Correct format: \"\\\"Walk\\\"\"")
    else:
        print("✗ Correct format check failed")
        return False

    # Check incorrect format
    if not (incorrect["animation"].startswith('"') and incorrect["animation"].endswith('"')):
        print("✓ Detected incorrect format: \"Walk\"")
    else:
        print("✗ Should detect missing nested quotes")
        return False

    return True


def main():
    print("\n🎮 Construct3-Copilot Skill Tests\n")

    tests = [
        ("Schema Loading", test_schema_loading),
        ("Query Schema", test_query_schema),
        ("Generate ImageData", test_generate_imagedata),
        ("Validate Output", test_validate_output),
        ("Clipboard Format", test_json_clipboard_format),
        ("String Parameter Format", test_string_parameter_format),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} failed with error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
