#!/usr/bin/env python3
"""
RAG HTTP bridge — queries the RAG service at http://localhost:8765.

Subcommands map to POST /search with the corresponding mode:
    search   → mode=semantic  (default full-text / hybrid)
    lookup   → mode=lookup    (exact ACE ID lookup)
    list     → mode=list      (list ACEs for a plugin)
    semantic → mode=semantic  (explicit semantic search)
    verify   → mode=lookup    (ACE ID verification alias)

Positional-only (no subcommand): mode=auto

Usage:
    python rag.py search "collision detection"
    python rag.py lookup "Sprite" --plugin sprite
    python rag.py list "Platform"
    python rag.py verify set-animation --plugin sprite
    python rag.py "fuzzy query"          # mode=auto
    python rag.py search "move" --plugin sprite --top-k 5 --scope eventsheet
    python rag.py search "addon SDK plugin" --collections addon_sdk
"""

import json
import sys
import urllib.error
import urllib.request

RAG_URL = "http://localhost:8765/search"
TIMEOUT = 120  # seconds — embedding + reranker on CPU can take 30-60s

SUBCOMMANDS = {
    "search": "semantic",
    "lookup": "lookup",
    "list": "list",
    "semantic": "semantic",
    "verify": "lookup",  # ACE ID verification → lookup mode
}


def _err(message: str, suggestion: str = "") -> str:
    payload: dict = {"error": message}
    if suggestion:
        payload["suggestion"] = suggestion
    return json.dumps(payload, ensure_ascii=False)


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
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        return 1, _err(
            f"RAG service offline: {reason}",
            "Start RAG: cd rag-service && python server.py  (or check infra/health.py)",
        )
    except json.JSONDecodeError as exc:
        return 1, _err(f"RAG returned invalid JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        return 1, _err(f"Unexpected error calling RAG: {exc}")


def _parse_args(argv: list[str]) -> tuple[int, str]:
    """
    Parse argv and call RAG.  Returns (exit_code, output_string).
    argv is sys.argv[1:].
    """
    if not argv:
        return 1, _err(
            "Missing query argument",
            "Usage: rag.py [search|lookup|list|semantic|verify] <query> [--plugin P] [--top-k N] [--scope S] [--collections C]",
        )

    # Determine subcommand / mode
    if argv[0] in SUBCOMMANDS:
        mode = SUBCOMMANDS[argv[0]]
        rest = argv[1:]
    else:
        mode = "auto"
        rest = argv[:]

    # Extract optional flags
    plugin: str | None = None
    top_k: int | None = None
    scope: str | None = None
    collections: list[str] | None = None
    positional: list[str] = []

    i = 0
    while i < len(rest):
        token = rest[i]
        if token == "--plugin" and i + 1 < len(rest):
            plugin = rest[i + 1]
            i += 2
        elif token == "--top-k" and i + 1 < len(rest):
            try:
                top_k = int(rest[i + 1])
            except ValueError:
                return 1, _err(f"--top-k must be an integer, got {rest[i+1]!r}")
            i += 2
        elif token == "--scope" and i + 1 < len(rest):
            scope = rest[i + 1]
            i += 2
        elif token == "--collections" and i + 1 < len(rest):
            collections = [c.strip() for c in rest[i + 1].split(",") if c.strip()]
            i += 2
        elif token.startswith("--"):
            return 1, _err(f"Unknown flag: {token}")
        else:
            positional.append(token)
            i += 1

    query = " ".join(positional).strip()
    if not query:
        return 1, _err(
            "Missing query argument",
            "Usage: rag.py [search|lookup|list|semantic|verify] <query> [--plugin P] [--top-k N] [--scope S] [--collections C]",
        )

    body: dict = {"query": query, "mode": mode}
    if plugin is not None:
        body["plugin"] = plugin
    if top_k is not None:
        body["top_k"] = top_k
    if scope is not None:
        body["scope"] = scope
    if collections is not None:
        body["collections"] = collections

    return _call_rag(body)


def main() -> None:
    exit_code, output = _parse_args(sys.argv[1:])
    print(output)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
