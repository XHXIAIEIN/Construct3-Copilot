#!/usr/bin/env python3
"""
Environment Health Check for Construct 3 Copilot

Verifies that all required data files and dependencies are available.

Usage:
    python health.py
"""

import json
import sys
from pathlib import Path


def check_health() -> dict:
    """Run all health checks and return a status report."""
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent.parent  # .claude/skills/construct3-copilot/
    project_root = skill_root.parent.parent.parent  # project root

    checks = {}

    # 1. Schema data
    schemas_dir = project_root / "data" / "schemas"
    plugins_dir = schemas_dir / "plugins"
    behaviors_dir = schemas_dir / "behaviors"
    checks["schemas_dir"] = {
        "path": str(schemas_dir),
        "exists": schemas_dir.exists(),
        "plugins": len(list(plugins_dir.glob("*.json"))) if plugins_dir.exists() else 0,
        "behaviors": len(list(behaviors_dir.glob("*.json"))) if behaviors_dir.exists() else 0,
    }

    # 2. Project analysis data (for examples.py)
    analysis_dir = project_root / "data" / "project_analysis"
    checks["project_analysis"] = {
        "path": str(analysis_dir),
        "exists": analysis_dir.exists(),
        "files": len(list(analysis_dir.glob("*.json"))) if analysis_dir.exists() else 0,
    }

    # 3. References
    refs_dir = skill_root / "references"
    checks["references"] = {
        "path": str(refs_dir),
        "exists": refs_dir.exists(),
        "files": len(list(refs_dir.glob("*.md"))) + len(list(refs_dir.glob("*.json"))) if refs_dir.exists() else 0,
    }

    # 4. Scripts integrity
    scripts_dir = skill_root / "scripts"
    required_scripts = [
        "query/schema.py",
        "query/examples.py",
        "generate/imagedata.py",
        "generate/layout.py",
        "validate/output.py",
    ]
    missing = [s for s in required_scripts if not (scripts_dir / s).exists()]
    checks["scripts"] = {
        "required": len(required_scripts),
        "missing": missing,
        "ok": len(missing) == 0,
    }

    # 5. Python version
    checks["python"] = {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ok": sys.version_info >= (3, 10),
    }

    # Overall status
    all_ok = (
        checks["schemas_dir"]["exists"]
        and checks["scripts"]["ok"]
        and checks["python"]["ok"]
    )

    return {"status": "ok" if all_ok else "degraded", "checks": checks}


def main():
    report = check_health()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
