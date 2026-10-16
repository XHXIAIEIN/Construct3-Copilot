# Service Integration Plan — Connect Copilot Skill to RAG + Clipboard Services

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Copilot Skill's scripts to the RAG (:8765) and Clipboard (:8766) services so Claude Code can use them as tools during generation, with graceful fallback when services are offline.

**Architecture:** Scripts act as HTTP bridge between Claude Code (orchestrator) and external services. Each script is a CLI tool: stdin/args in → stdout JSON out → exit code signals success/failure. `health.py` probes all services on startup. `rag.py` calls RAG `/search`. `clipboard_service.py` calls Clipboard `/validate` and `/generate`. SKILL.md routes Claude to prefer services when available.

**Tech Stack:** Python 3.11+, httpx (HTTP client), existing FastAPI services

**Dependencies between tasks:** Task 1 (health) is independent. Task 2 (rag) and Task 3 (clipboard) depend on health detection pattern but can be built in parallel. Task 4 (SKILL.md wiring) depends on all three.

---

## File Structure

| File | Responsibility | New/Modify |
|------|---------------|------------|
| `scripts/infra/health.py` | Probe RAG :8765 + Clipboard :8766 + local data | **Rewrite** |
| `scripts/query/rag.py` | Call RAG `/search`, format results for Claude | **Rewrite** |
| `scripts/generate/clipboard_service.py` | Call Clipboard `/validate` and `/generate` | **New** |
| `SKILL.md` | Route Claude to services when available | **Modify** |
| `CLAUDE.md` | Update workflow to include service calls | **Modify** |
| `tests/test_service_integration.py` | Unit tests (mock httpx, no live services) | **New** |

---

### Task 1: Rewrite `health.py` — Service Discovery

**Files:**
- Rewrite: `.claude/skills/construct3-copilot/scripts/infra/health.py`
- Create: `tests/test_service_integration.py`

- [ ] **Step 1: Write failing test for health check**

```python
# tests/test_service_integration.py
"""Service integration tests — no live services required."""
import json
import subprocess
import sys
from unittest.mock import patch, AsyncMock
import pytest

SCRIPTS = ".claude/skills/construct3-copilot/scripts"


class TestHealthCheck:
    def test_health_outputs_valid_json(self):
        """health.py must always produce valid JSON, even if services are down."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/infra/health.py"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        assert "status" in data
        assert "services" in data
        assert "rag" in data["services"]
        assert "clipboard" in data["services"]
        for svc in data["services"].values():
            assert "url" in svc
            assert "available" in svc

    def test_health_exits_zero_even_when_degraded(self):
        """health.py always exits 0 — degraded is not an error."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/infra/health.py"],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_integration.py::TestHealthCheck -v`
Expected: FAIL — current health.py output doesn't have `services` key

- [ ] **Step 3: Implement health.py**

```python
#!/usr/bin/env python3
"""
Service Discovery for Construct 3 Copilot

Probes external services and local data availability.
Always exits 0 — degraded state is normal, not an error.

Usage:
    python health.py           # Full report
    python health.py --brief   # One-line summary
"""
import json
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


RAG_URL = "http://localhost:8765"
CLIPBOARD_URL = "http://localhost:8766"
TIMEOUT = 3  # seconds


def probe(url: str) -> dict:
    """Probe a service health endpoint. Returns {available, status, detail}."""
    try:
        req = Request(f"{url}/health", method="GET")
        with urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read())
            return {"url": url, "available": True, "status": body.get("status", "ok")}
    except (URLError, OSError, json.JSONDecodeError) as e:
        return {"url": url, "available": False, "status": "offline", "error": str(e)}


def check_local_data() -> dict:
    """Check local schema files availability."""
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent.parent
    project_root = skill_root.parent.parent.parent

    schemas_dir = project_root / "data" / "schemas"
    plugins_count = len(list((schemas_dir / "plugins").glob("*.json"))) if (schemas_dir / "plugins").exists() else 0
    return {
        "schemas_dir": str(schemas_dir),
        "available": schemas_dir.exists() and plugins_count > 0,
        "plugins": plugins_count,
    }


def main():
    brief = "--brief" in sys.argv

    rag = probe(RAG_URL)
    clipboard = probe(CLIPBOARD_URL)
    local = check_local_data()

    report = {
        "status": "ok" if (rag["available"] or local["available"]) else "degraded",
        "services": {
            "rag": rag,
            "clipboard": clipboard,
        },
        "local_data": local,
    }

    if brief:
        rag_icon = "+" if rag["available"] else "-"
        clip_icon = "+" if clipboard["available"] else "-"
        local_icon = "+" if local["available"] else "-"
        print(f"RAG:{rag_icon} Clipboard:{clip_icon} Local:{local_icon}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_integration.py::TestHealthCheck -v`
Expected: PASS (services will be offline in test, but output format is correct)

- [ ] **Step 5: Commit**

```bash
git add scripts/infra/health.py tests/test_service_integration.py
git commit -m "feat: rewrite health.py with service discovery for RAG + Clipboard"
```

---

### Task 2: Rewrite `rag.py` — RAG Service Bridge

**Files:**
- Rewrite: `.claude/skills/construct3-copilot/scripts/query/rag.py`
- Modify: `tests/test_service_integration.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_service_integration.py`:

```python
class TestRagBridge:
    def test_rag_offline_exits_nonzero(self):
        """When RAG is offline, rag.py exits 1 with error JSON."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/query/rag.py", "collision detection"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        assert "error" in data
        assert result.returncode == 1

    def test_rag_missing_query_exits_nonzero(self):
        """rag.py with no arguments exits 1."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/query/rag.py"],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 1

    def test_rag_output_is_valid_json(self):
        """Even on failure, rag.py outputs valid JSON."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/query/rag.py", "test query"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_service_integration.py::TestRagBridge -v`
Expected: FAIL — current rag.py returns empty list, not error dict

- [ ] **Step 3: Implement rag.py**

```python
#!/usr/bin/env python3
"""
RAG Service Bridge — Search Construct 3 documentation via RAG API

Calls the Construct3-RAG service at localhost:8765 for ACE lookup
and semantic search. Falls back to error JSON when service is offline.

Usage:
    python rag.py search "collision detection"
    python rag.py lookup "Sprite" --plugin sprite
    python rag.py list "Platform"
    python rag.py verify <ace-id> --plugin <plugin>
"""
import json
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError


RAG_URL = "http://localhost:8765"
TIMEOUT = 10  # seconds — semantic search can be slow


def call_rag(query: str, mode: str = "auto", **kwargs) -> dict:
    """Call RAG /search endpoint. Returns parsed response or error dict."""
    payload = {"query": query, "mode": mode}
    for k, v in kwargs.items():
        if v is not None:
            payload[k] = v

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{RAG_URL}/search",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except URLError as e:
        return {"error": f"RAG service offline: {e}", "suggestion": "Start RAG: cd Construct3-RAG && python -m uvicorn src.api:app --port 8765"}
    except json.JSONDecodeError as e:
        return {"error": f"RAG returned invalid JSON: {e}"}


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "Usage: rag.py <mode> <query> [--plugin P] [--top-k N] [--scope S]"}))
        sys.exit(1)

    # Parse subcommand
    mode = args[0] if args[0] in ("search", "lookup", "list", "semantic", "verify") else "auto"
    query_parts = []
    plugin = None
    top_k = None
    scope = None
    i = 1 if mode != "auto" else 0

    while i < len(args):
        if args[i] == "--plugin" and i + 1 < len(args):
            plugin = args[i + 1]
            i += 2
        elif args[i] == "--top-k" and i + 1 < len(args):
            top_k = int(args[i + 1])
            i += 2
        elif args[i] == "--scope" and i + 1 < len(args):
            scope = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)

    # Map 'verify' to a targeted lookup
    if mode == "verify":
        mode = "lookup"

    result = call_rag(query, mode=mode, plugin=plugin, top_k=top_k, scope=scope)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1 if "error" in result else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_service_integration.py::TestRagBridge -v`
Expected: PASS (RAG offline → exits 1 with error JSON)

- [ ] **Step 5: Commit**

```bash
git add scripts/query/rag.py tests/test_service_integration.py
git commit -m "feat: rewrite rag.py as HTTP bridge to RAG :8765 service"
```

---

### Task 3: Create `clipboard_service.py` — Clipboard Service Bridge

**Files:**
- Create: `.claude/skills/construct3-copilot/scripts/generate/clipboard_service.py`
- Modify: `tests/test_service_integration.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_service_integration.py`:

```python
class TestClipboardBridge:
    def test_clipboard_validate_offline_exits_nonzero(self):
        """When Clipboard service is offline, exits 1 with error JSON."""
        sample = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/generate/clipboard_service.py", "validate", sample],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        assert "error" in data
        assert result.returncode == 1

    def test_clipboard_missing_args_exits_nonzero(self):
        """clipboard_service.py with no arguments exits 1."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/generate/clipboard_service.py"],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 1

    def test_clipboard_output_is_valid_json(self):
        """Even on failure, clipboard_service.py outputs valid JSON."""
        result = subprocess.run(
            [sys.executable, f"{SCRIPTS}/generate/clipboard_service.py", "validate", "{}"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_service_integration.py::TestClipboardBridge -v`
Expected: FAIL — file does not exist

- [ ] **Step 3: Implement clipboard_service.py**

```python
#!/usr/bin/env python3
"""
Clipboard Service Bridge — Validate and generate C3 JSON via Clipboard API

Calls the Construct3-Clipboard service at localhost:8766 for structural
validation and Intent IR → clipboard JSON generation.

Usage:
    python clipboard_service.py validate '<clipboard-json>'
    python clipboard_service.py validate clipboard.json
    python clipboard_service.py generate '<intent-ir-json>'
    python clipboard_service.py generate intent.json
    python clipboard_service.py health
"""
import json
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError


CLIPBOARD_URL = "http://localhost:8766"
TIMEOUT = 10


def call_clipboard(endpoint: str, payload: dict) -> dict:
    """Call Clipboard service endpoint. Returns parsed response or error dict."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{CLIPBOARD_URL}/{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except URLError as e:
        return {"error": f"Clipboard service offline: {e}", "suggestion": "Start: cd Construct3-Clipboard && python -m uvicorn src.api:app --port 8766"}
    except json.JSONDecodeError as e:
        return {"error": f"Clipboard service returned invalid JSON: {e}"}


def cmd_validate(json_str: str) -> dict:
    """Validate clipboard JSON via Clipboard service."""
    try:
        clipboard_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON input: {e}"}
    return call_clipboard("validate", {"clipboard_json": clipboard_json})


def cmd_generate(json_str: str) -> dict:
    """Generate clipboard JSON from Intent IR via Clipboard service."""
    try:
        intent_ir = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid Intent IR JSON: {e}"}
    return call_clipboard("generate", {"intent_ir": intent_ir})


def cmd_health() -> dict:
    """Check Clipboard service health."""
    try:
        req = Request(f"{CLIPBOARD_URL}/health", method="GET")
        with urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except (URLError, json.JSONDecodeError) as e:
        return {"error": f"Clipboard service offline: {e}"}


def read_input(arg: str) -> str:
    """Read JSON from argument — either a file path or inline JSON string."""
    if arg.endswith(".json"):
        with open(arg, "r", encoding="utf-8") as f:
            return f.read()
    return arg


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "Usage: clipboard_service.py <validate|generate|health> [json-or-file]"}))
        sys.exit(1)

    cmd = args[0]

    if cmd == "health":
        result = cmd_health()
    elif cmd == "validate" and len(args) > 1:
        result = cmd_validate(read_input(args[1]))
    elif cmd == "generate" and len(args) > 1:
        result = cmd_generate(read_input(args[1]))
    else:
        result = {"error": f"Unknown command or missing argument: {cmd}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))

    has_error = "error" in result or (isinstance(result.get("passed"), bool) and not result["passed"])
    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_service_integration.py::TestClipboardBridge -v`
Expected: PASS (service offline → exits 1 with error JSON)

- [ ] **Step 5: Commit**

```bash
git add scripts/generate/clipboard_service.py tests/test_service_integration.py
git commit -m "feat: add clipboard_service.py bridge to Clipboard :8766"
```

---

### Task 4: Wire Services into SKILL.md and CLAUDE.md

**Files:**
- Modify: `.claude/skills/construct3-copilot/SKILL.md`
- Modify: `.claude/skills/construct3-copilot/CLAUDE.md`

- [ ] **Step 1: Update SKILL.md Script Toolkit section**

Replace the `## 2. Script Toolkit` section in SKILL.md with:

```markdown
## 2. Script Toolkit

All scripts: stdout = structured data, stderr = logs, exit 0 = success. `query/` scripts are read-only and safe to run in parallel.

### Service Discovery (run first)

```bash
# Check which services are available
python3 scripts/infra/health.py --brief
# Output: RAG:+ Clipboard:+ Local:+  (+ = available, - = offline)

# Full status report
python3 scripts/infra/health.py
```

### ACE Schema Lookup

```bash
# Local lookup — MANDATORY, always available
python3 scripts/query/schema.py search {keyword}
python3 scripts/query/schema.py plugin {name} {ace-id}
python3 scripts/query/schema.py behavior {name} {ace-id}

# RAG semantic search — when RAG is online, use for fuzzy/Chinese queries
python3 scripts/query/rag.py search "how to detect collision"
python3 scripts/query/rag.py lookup "Sprite" --plugin sprite
python3 scripts/query/rag.py list "Platform"
```

### JSON Generation

```bash
# Local generation (placeholder art, layout presets)
python3 scripts/generate/imagedata.py --color {color} --width {W} --height {H}
python3 scripts/generate/layout.py --preset {platformer|breakout} -W {W} -H {H}

# Clipboard service — when online, use for IR → validated JSON
python3 scripts/generate/clipboard_service.py generate '<intent-ir-json>'
python3 scripts/generate/clipboard_service.py validate '<clipboard-json>'
```

### Validation

```bash
# Local validation — MANDATORY, always run before delivery
python3 scripts/validate/output.py '<json>'

# Clipboard service validation — when online, use as second opinion
python3 scripts/generate/clipboard_service.py validate '<json>'
```
```

- [ ] **Step 2: Update CLAUDE.md Mandatory Workflow section**

Replace the `## Mandatory Workflow` section in CLAUDE.md with:

```markdown
## Mandatory Workflow

```
DISCOVER → QUERY → GENERATE → VALIDATE → FIX
```

0. **Discover**: Run `scripts/infra/health.py --brief` to check service availability
1. **Query**: `scripts/query/schema.py` for every ACE ID (mandatory, local)
   - When RAG is online: also run `scripts/query/rag.py search` for semantic context
2. **Generate**: Author JSON directly or use `scripts/generate/clipboard_service.py generate` when Clipboard service is online
3. **Validate**: `scripts/validate/output.py '<json>'` (mandatory, local) — fail = do not deliver
   - When Clipboard service is online: also run `scripts/generate/clipboard_service.py validate` for structural validation
4. **Fix**: On validation failure, fix and re-validate (loop step 3, max 3 retries)
```

- [ ] **Step 3: Commit**

```bash
git add SKILL.md CLAUDE.md
git commit -m "feat: wire RAG + Clipboard services into skill routing"
```

---

### Task 5: Update CI Workflow

**Files:**
- Modify: `.github/workflows/validate-agents-skill.yml`

- [ ] **Step 1: Add smoke test for new scripts**

Add to the `Smoke test skill scripts` step:

```yaml
      - name: Smoke test skill scripts
        run: |
          python .claude/skills/construct3-copilot/scripts/query/schema.py search collision
          python .claude/skills/construct3-copilot/scripts/validate/output.py tests/fixtures/events_basic.json
          python .claude/skills/construct3-copilot/scripts/infra/health.py --brief
          # These exit 1 when services are offline — expected in CI
          python .claude/skills/construct3-copilot/scripts/query/rag.py search collision || true
          python .claude/skills/construct3-copilot/scripts/generate/clipboard_service.py health || true

      - name: Run integration tests
        run: |
          python -m pytest tests/test_service_integration.py -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/validate-agents-skill.yml
git commit -m "ci: add smoke tests for service bridge scripts"
```

---

## Degradation Matrix

| RAG | Clipboard | Behavior |
|-----|-----------|----------|
| online | online | Full pipeline: RAG semantic search → Clipboard generate → dual validate |
| online | offline | RAG enriches context, Claude generates JSON, local validate only |
| offline | online | Local schema.py only, Clipboard generate + validate |
| offline | offline | Current behavior: local schema.py + Claude generates + local validate |

All four states produce valid output. Services enhance quality but are never required.
