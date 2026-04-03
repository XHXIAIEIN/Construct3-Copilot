#!/usr/bin/env python3
"""
Service health check for Construct 3 Copilot.

Probes RAG service, Clipboard service, and local schema data.
Always exits 0 — degraded state is not an error.

Usage:
    python health.py          # full JSON report
    python health.py --brief  # one-line summary: RAG:+ Clipboard:- Local:+
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

RAG_URL = "http://localhost:8765"
CLIPBOARD_URL = "http://localhost:8766"
PROBE_TIMEOUT = 3  # seconds


def probe_service(base_url: str) -> dict:
    """Probe a service's /health endpoint. Returns dict with available + status."""
    health_url = base_url.rstrip("/") + "/health"
    try:
        with urlopen(health_url, timeout=PROBE_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
                status = data.get("status", "ok")
            except (json.JSONDecodeError, AttributeError):
                status = "ok"
            return {"url": base_url, "available": True, "status": str(status)}
    except (URLError, OSError, TimeoutError) as exc:
        return {"url": base_url, "available": False, "status": str(exc)}


def check_local_data() -> dict:
    """Check local schema data directory."""
    # Resolve project root relative to this script:
    # scripts/infra/health.py -> scripts -> .claude/skills/construct3-copilot -> skill_root
    # skill_root -> .claude/skills -> .claude -> project_root
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent.parent  # .claude/skills/construct3-copilot/
    project_root = skill_root.parent.parent.parent  # project root

    plugins_dir = project_root / "data" / "schemas" / "plugins"
    if plugins_dir.exists():
        plugin_count = len(list(plugins_dir.glob("*.json")))
        available = plugin_count > 0
    else:
        plugin_count = 0
        available = False

    return {
        "schemas_dir": str(plugins_dir),
        "available": available,
        "plugins": plugin_count,
    }


def build_report() -> dict:
    rag = probe_service(RAG_URL)
    clipboard = probe_service(CLIPBOARD_URL)
    local = check_local_data()

    all_ok = rag["available"] and clipboard["available"] and local["available"]

    return {
        "status": "ok" if all_ok else "degraded",
        "services": {
            "rag": rag,
            "clipboard": clipboard,
        },
        "local_data": local,
    }


def brief_line(report: dict) -> str:
    """Format one-line summary like: RAG:+ Clipboard:- Local:+"""

    def sym(val: bool) -> str:
        return "+" if val else "-"

    rag_sym = sym(report["services"]["rag"]["available"])
    cb_sym = sym(report["services"]["clipboard"]["available"])
    local_sym = sym(report["local_data"]["available"])
    return f"RAG:{rag_sym} Clipboard:{cb_sym} Local:{local_sym}"


def main():
    parser = argparse.ArgumentParser(description="Construct 3 Copilot service health check")
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Output one-line summary instead of JSON",
    )
    args = parser.parse_args()

    report = build_report()

    if args.brief:
        print(brief_line(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    # Always exit 0 — degraded is informational, not an error
    sys.exit(0)


if __name__ == "__main__":
    main()
