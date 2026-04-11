#!/usr/bin/env python3
"""
Clipboard HTTP bridge — interacts with the Construct3-Clipboard service at http://localhost:8766.

Subcommands:
    validate  — POST /validate   (validate existing clipboard JSON)
               --local flag: local pre-validation only (no network)
    generate  — POST /generate   (generate clipboard JSON from Intent IR)
    health    — GET  /health     (check service health)

Usage:
    python clipboard_service.py validate '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
    python clipboard_service.py validate clipboard.json
    python clipboard_service.py generate '{"type":"event_sheet","events":[...]}'
    python clipboard_service.py generate intent.json
    python clipboard_service.py health
"""

import json
import sys
import urllib.error
import urllib.request

import os

CLIPBOARD_PORT = os.environ.get("C3_CLIPBOARD_PORT", "8766")
CLIPBOARD_BASE_URL = f"http://localhost:{CLIPBOARD_PORT}"
TIMEOUT = 10  # seconds — validation/generation calls are fast

_START_SUGGESTION = "Start: cd Construct3-Clipboard && python -m uvicorn src.api:app --port 8766"


def _err(message: str, suggestion: str = "") -> str:
    payload: dict = {"error": message}
    if suggestion:
        payload["suggestion"] = suggestion
    return json.dumps(payload, ensure_ascii=False)


def _load_json_arg(arg: str) -> tuple[int, str, dict | None]:
    """
    Accept either an inline JSON string or a path to a .json file.
    Returns (exit_code, error_string_or_empty, parsed_dict_or_None).
    """
    # Try inline JSON first
    stripped = arg.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return 0, "", json.loads(stripped)
        except json.JSONDecodeError as exc:
            return 1, _err(f"Invalid JSON argument: {exc}"), None

    # Treat as file path
    try:
        with open(arg, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return 0, "", data
    except FileNotFoundError:
        return 1, _err(f"File not found: {arg!r}"), None
    except json.JSONDecodeError as exc:
        return 1, _err(f"File {arg!r} contains invalid JSON: {exc}"), None
    except OSError as exc:
        return 1, _err(f"Cannot read file {arg!r}: {exc}"), None


def _http_post(path: str, body: dict) -> tuple[int, str]:
    """POST JSON body to the clipboard service. Returns (exit_code, json_string)."""
    url = CLIPBOARD_BASE_URL + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            json.loads(raw)  # validate response is JSON
            return 0, raw
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        return 1, _err(f"Clipboard service offline: {reason}", _START_SUGGESTION)
    except json.JSONDecodeError as exc:
        return 1, _err(f"Clipboard service returned invalid JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        return 1, _err(f"Unexpected error calling Clipboard service: {exc}")


def _http_get(path: str) -> tuple[int, str]:
    """GET from the clipboard service. Returns (exit_code, json_string)."""
    url = CLIPBOARD_BASE_URL + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            json.loads(raw)  # validate response is JSON
            return 0, raw
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        return 1, _err(f"Clipboard service offline: {reason}", _START_SUGGESTION)
    except json.JSONDecodeError as exc:
        return 1, _err(f"Clipboard service returned invalid JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        return 1, _err(f"Unexpected error calling Clipboard service: {exc}")


def cmd_validate(args: list[str]) -> tuple[int, str]:
    # Check for --local flag
    local_mode = "--local" in args
    clean_args = [a for a in args if a != "--local"]

    if not clean_args:
        return 1, _err(
            "Missing clipboard JSON argument",
            "Usage: clipboard_service.py validate [--local] '<json>' | <file.json>",
        )

    code, err_str, body = _load_json_arg(clean_args[0])
    if code != 0:
        return code, err_str

    if local_mode:
        # Local pre-validation only — no network call
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prevalidate",
            os.path.join(os.path.dirname(__file__), "prevalidate.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.prevalidate(body)
        result["mode"] = "local"
        return (0 if result["passed"] else 1), json.dumps(result, ensure_ascii=False)

    exit_code, response_str = _http_post("/validate", {"clipboard_json": body})
    if exit_code != 0:
        return exit_code, response_str

    # Check validation result: passed=false → exit 1 but still print the response
    try:
        response = json.loads(response_str)
        if not response.get("passed", True):
            return 1, response_str
    except json.JSONDecodeError:
        pass  # already validated above; won't happen

    return 0, response_str


def cmd_generate(args: list[str]) -> tuple[int, str]:
    if not args:
        return 1, _err(
            "Missing Intent IR JSON argument",
            "Usage: clipboard_service.py generate '<intent_ir_json>' | <file.json>",
        )

    code, err_str, body = _load_json_arg(args[0])
    if code != 0:
        return code, err_str

    exit_code, response_str = _http_post("/generate", {"intent_ir": body})
    if exit_code != 0:
        return exit_code, response_str

    # Check success field
    try:
        response = json.loads(response_str)
        if not response.get("success", True):
            return 1, response_str
    except json.JSONDecodeError:
        pass

    return 0, response_str


def cmd_health(_args: list[str]) -> tuple[int, str]:
    return _http_get("/health")


COMMANDS = {
    "validate": cmd_validate,
    "generate": cmd_generate,
    "health": cmd_health,
}


def main() -> None:
    argv = sys.argv[1:]

    if not argv:
        print(_err(
            "Missing subcommand",
            "Usage: clipboard_service.py [validate|generate|health] [args...]",
        ))
        sys.exit(1)

    subcommand = argv[0]
    if subcommand not in COMMANDS:
        print(_err(
            f"Unknown subcommand: {subcommand!r}",
            "Available: validate, generate, health",
        ))
        sys.exit(1)

    exit_code, output = COMMANDS[subcommand](argv[1:])
    print(output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
