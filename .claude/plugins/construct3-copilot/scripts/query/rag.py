#!/usr/bin/env python3
"""
RAG HTTP bridge — queries the Construct3-RAG lookup service (default port 8765).

The service answers from the ACE schemas: which ACEs an addon has, with their
IDs, names and parameters. It declines how-to and concept questions with an
HTTP 200 that has no "lookup" section. Those are answered by reading the
Construct3-Manual clone or the example projects; asking again returns the same.

Subcommands and the POST /search mode they send:
    search   → mode=auto    (the service treats auto as lookup)
    lookup   → mode=lookup  (match objects: ace_id, names, params)
    list     → mode=list    (ACE display names of one addon, by type)
    verify   → mode=lookup  (exact ACE ID check; exit 1 when the ID is absent)

Positional-only (no subcommand): mode=auto

A query names the addon by id or display name, then keywords from the ACE name.

Usage:
    python rag.py search "Sprite collision"
    python rag.py lookup "Keyboard key down" --lang zh
    python rag.py lookup "Platform jump" --scope scripts
    python rag.py list "8 Direction"
    python rag.py verify sprite:set-animation
    python rag.py "Sprite collision"          # mode=auto
"""

import difflib
import json
import sys
import urllib.error
import urllib.request

import os

RAG_PORT = os.environ.get("C3_RAG_PORT", "8765")
# 127.0.0.1, not localhost: Windows tries ::1 first, uvicorn listens on IPv4
# only by default, and every call would wait about 2 s for that refusal.
RAG_URL = f"http://127.0.0.1:{RAG_PORT}/search"
TIMEOUT = 30  # seconds — a lookup answers in milliseconds; this bounds a hung service

SUBCOMMANDS = {
    "search": "auto",
    "lookup": "lookup",
    "list": "list",
    "verify": "lookup",
}

# The request model forbids unknown fields and values, so both are checked here.
SCOPES = ("eventsheet", "scripts", "js", "ts", "all")
LANGS = ("en", "zh", "ja", "ko")
MAX_QUERY_CHARS = 500

ACE_TYPES = ("conditions", "actions", "expressions")
COMMON = "_common"  # addon id of the ACEs shared by every world object

USAGE = (
    'Usage: rag.py [search|lookup|list] "<addon> [keywords]" [--scope S] [--lang L]'
    "  |  rag.py verify <addon>:<ace-id> [--lang L]"
)
READ_INSTEAD = (
    "For a how-to or concept question, read ../Construct3-Manual or "
    "../Construct-Example-Projects."
)
NO_LOOKUP_HINT = (
    "rag.py: no lookup section. The service found no ACE or declined the question; "
    "this does not mean the feature is missing. Name the addon first: "
    '"<addon> <keywords>", or list <addon>. ' + READ_INSTEAD
)

# Flags the service has no field for. Each fails here with what to do instead;
# --plugin gets its replacement command from the arguments.
UNSUPPORTED_FLAGS = {
    "--plugin": "",
    "--top-k": "Drop the flag: a lookup returns every match. Narrow the query with keywords.",
    "--collections": (
        "The service holds ACE schemas only. Read the clones instead: ../Construct3-Manual, "
        "../Construct-Addon-SDK, ../Construct-Example-Projects."
    ),
}


def _err(message: str, suggestion: str = "") -> str:
    payload: dict = {"error": message}
    if suggestion:
        payload["suggestion"] = suggestion
    return json.dumps(payload, ensure_ascii=False)


def _http_error_reason(exc: urllib.error.HTTPError) -> str:
    """The service's own reason for an error status, on one line."""
    try:
        detail = json.loads(exc.read().decode("utf-8", errors="replace")).get("detail")
    except (OSError, ValueError, AttributeError):
        return ""
    if isinstance(detail, list):  # FastAPI validation errors
        return "; ".join(
            f"{'.'.join(str(part) for part in item.get('loc', []))}: {item.get('msg', '')}"
            for item in detail
            if isinstance(item, dict)
        )
    return str(detail or "")


def _call_rag(body: dict) -> tuple[int, str]:
    """POST to RAG service. Returns (exit_code, json_string)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        RAG_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            # Validate it's JSON before returning
            json.loads(raw)
            return 0, raw
    # HTTPError subclasses URLError: caught first, or an error status reads as "offline".
    except urllib.error.HTTPError as exc:
        reason = _http_error_reason(exc)
        return 1, _err(
            f"RAG answered HTTP {exc.code}" + (f": {reason}" if reason else ""),
            "The service is running; check the request. " + USAGE,
        )
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        return 1, _err(
            f"RAG service offline: {reason}",
            "Start RAG: cd ../Construct3-RAG && python -m uvicorn src.api:app "
            f"--port {RAG_PORT}  (first run: python scripts/setup.py; status: infra/health.py)",
        )
    except json.JSONDecodeError as exc:
        return 1, _err(f"RAG returned invalid JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        return 1, _err(f"Unexpected error calling RAG: {exc}")


def _body(query: str, mode: str, scope: str | None, lang: str | None) -> dict:
    body: dict = {"query": query, "mode": mode}
    if scope is not None:
        body["scope"] = scope
    if lang is not None:
        body["lang"] = lang
    return body


def _query(body: dict) -> tuple[int, str]:
    """Pass the service's answer through; say so on stderr when it has no lookup section."""
    exit_code, output = _call_rag(body)
    if exit_code == 0 and not json.loads(output).get("lookup"):
        print(NO_LOOKUP_HINT, file=sys.stderr)
    return exit_code, output


def _aces(response: dict) -> list[dict]:
    """Every ACE of a lookup response, flattened with its addon id and ACE type."""
    matches = (response.get("lookup") or {}).get("matches") or {}
    return [
        {"addon": addon_id, "ace_type": ace_type, **item}
        for addon_id, groups in matches.items()
        for ace_type in ACE_TYPES
        for item in groups.get(ace_type, [])
    ]


def _nearest(ace_id: str, known: list[dict]) -> list[str]:
    """Existing "<addon>:<ace-id>" targets that contain ace_id or are spelled close to it."""
    targets = {f"{ace['addon']}:{ace['ace_id']}": ace["ace_id"] for ace in known}
    containing = [target for target, known_id in targets.items() if ace_id in known_id]
    close_ids = difflib.get_close_matches(ace_id, sorted(set(targets.values())), n=5, cutoff=0.6)
    close = [
        target
        for close_id in close_ids
        for target, known_id in targets.items()
        if known_id == close_id
    ]
    return list(dict.fromkeys(containing + close))[:5]


def _verify(target: str, scope: str | None, lang: str | None) -> tuple[int, str]:
    """
    Exact ACE ID check. Reads the addon's whole ACE set and compares IDs here:
    the service's own "<addon>:<ace-id>" form answers with the first ID that
    contains the text, so toggle-boolean would pass as toggle-boolean-eventvar.
    """
    addon, _, ace_id = target.rpartition(":")
    addon, ace_id = addon.strip(), ace_id.strip()
    if not addon or not ace_id:
        return 1, _err(
            "verify needs <addon>:<ace-id>",
            "Example: rag.py verify sprite:set-animation",
        )

    exit_code, output = _call_rag(_body(addon, "lookup", scope, lang))
    if exit_code != 0:
        return exit_code, output
    own = _aces(json.loads(output))
    found = [ace for ace in own if ace["ace_id"] == ace_id]
    if found:
        return 0, json.dumps({"verified": True, "matches": found}, ensure_ascii=False)

    common: list[dict] = []
    asked_for_common = any(ace["addon"] == COMMON for ace in own)
    if not asked_for_common:
        exit_code, output = _call_rag(_body(COMMON, "lookup", scope, lang))
        if exit_code != 0:
            return exit_code, output
        common = _aces(json.loads(output))
    in_common = [ace for ace in common if ace["ace_id"] == ace_id]

    # An addon the service does not know verifies nothing, common ACE or not.
    if own and in_common:
        note = (
            f"{ace_id} is not one of {addon}'s own ACEs. It is a common ACE, "
            "shared by world objects (objects placed in a layout) only."
        )
        result = {"verified": True, "matches": in_common, "note": note}
        return 0, json.dumps(result, ensure_ascii=False)

    if own:
        where = "the common ACEs" if asked_for_common else f"{addon} or in the common ACEs"
        message = f"No ACE with the id {ace_id!r} in {where}"
        suggestion = f'See what {addon} has: rag.py list "{addon}"'
    else:
        message = f"Addon {addon!r} not recognized"
        suggestion = (
            "Use the addon id or its English display name, such as EightDir or "
            '"8 Direction". The manual lists them: ../Construct3-Manual/Construct3-Manual/'
            "plugin-reference.md and behavior-reference.md"
        )
        if in_common:
            suggestion = (
                f"{ace_id} is a common ACE of world objects: verify it under the object's "
                f"plugin, as in rag.py verify sprite:{ace_id}. " + suggestion
            )
    payload = {"verified": False, "error": message, "suggestion": suggestion}
    nearest = _nearest(ace_id, own + common)
    if nearest:
        payload["nearest"] = nearest
    return 1, json.dumps(payload, ensure_ascii=False)


def _unsupported_flag(flag: str, value: str, command: str, query: str) -> tuple[int, str]:
    suggestion = UNSUPPORTED_FLAGS[flag]
    if flag == "--plugin":
        addon = value or "<addon>"
        if command == "verify":
            suggestion = f"Run: rag.py verify {addon}:{query or '<ace-id>'}"
        else:
            suggestion = (
                f'Name the addon in the query: rag.py {command or "search"} "{addon} <keywords>". '
                f"To check an ACE ID: rag.py verify {addon}:<ace-id>"
            )
    return 1, _err(f"{flag} is not supported by the lookup service", suggestion)


def _parse_args(argv: list[str]) -> tuple[int, str]:
    """
    Parse argv and call RAG.  Returns (exit_code, output_string).
    argv is sys.argv[1:].
    """
    if not argv:
        return 1, _err("Missing query argument", USAGE)

    # Without this, "semantic" would be sent as the first word of an auto query.
    if argv[0] == "semantic":
        return 1, _err(
            "The semantic subcommand is not supported: the service only looks ACEs up",
            'For an ACE: rag.py search "<addon> <keywords>". ' + READ_INSTEAD,
        )

    # Determine subcommand / mode
    if argv[0] in SUBCOMMANDS:
        command = argv[0]
        rest = argv[1:]
    else:
        command = ""
        rest = argv[:]
    mode = SUBCOMMANDS.get(command, "auto")

    # Extract optional flags
    options: dict[str, str] = {}
    unsupported: tuple[str, str] | None = None
    positional: list[str] = []

    i = 0
    while i < len(rest):
        token = rest[i]
        value = rest[i + 1] if i + 1 < len(rest) else ""
        if value.startswith("--"):
            value = ""
        if token in UNSUPPORTED_FLAGS:
            unsupported = unsupported or (token, value)
            i += 2 if value else 1
        elif token in ("--scope", "--lang"):
            if not value:
                return 1, _err(f"{token} needs a value", USAGE)
            options[token] = value
            i += 2
        elif token.startswith("--"):
            return 1, _err(f"Unknown flag: {token}", USAGE)
        else:
            positional.append(token)
            i += 1

    query = " ".join(positional).strip()
    if unsupported:
        return _unsupported_flag(*unsupported, command, query)
    if not query:
        return 1, _err("Missing query argument", USAGE)
    if len(query) > MAX_QUERY_CHARS:
        return 1, _err(
            f"Query is {len(query)} characters; the service accepts {MAX_QUERY_CHARS}",
            'A query is short: "<addon> <keywords>". ' + READ_INSTEAD,
        )

    scope = options.get("--scope")
    if scope is not None and scope not in SCOPES:
        return 1, _err(f"--scope must be one of {', '.join(SCOPES)}; got {scope!r}")
    lang = options.get("--lang")
    if lang is not None and lang not in LANGS:
        return 1, _err(f"--lang must be one of {', '.join(LANGS)}; got {lang!r}")

    if command == "verify":
        return _verify(query, scope, lang)
    return _query(_body(query, mode, scope, lang))


def main() -> None:
    exit_code, output = _parse_args(sys.argv[1:])
    print(output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
