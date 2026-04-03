"""
Integration tests for health.py service discovery script and rag.py RAG bridge.

Tests run without live services — all service probes are expected to fail/timeout,
and the scripts must still produce valid JSON output with appropriate exit codes.

Note on Windows subprocess handle limits: subprocess.run opens three pipe handles
(stdin, stdout, stderr) per call.  Running many tests that each spawn a new child
process can exhaust the available inheritable handles before pytest finishes.
We therefore cache script results at module level so that each unique
(script, args) combination only spawns one subprocess across the whole suite.
"""

import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

HEALTH_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude/skills/construct3-copilot/scripts/infra/health.py"
)


_RESULT_CACHE: dict = {}


def _run_cached(cmd_tuple: tuple, timeout: int = 30):
    """Run a command once and cache the result. cmd_tuple must be hashable.

    Uses subprocess.DEVNULL for stdin to avoid inheriting invalid handle 0
    from the pytest process on Windows (Python 3.14 subprocess handle bug).
    """
    if cmd_tuple in _RESULT_CACHE:
        return _RESULT_CACHE[cmd_tuple]
    result = subprocess.run(
        list(cmd_tuple),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    _RESULT_CACHE[cmd_tuple] = (result.returncode, result.stdout, result.stderr)
    return _RESULT_CACHE[cmd_tuple]


def run_health(extra_args=None):
    """Run health.py and return (returncode, stdout, stderr). Results are cached."""
    cmd = tuple([sys.executable, str(HEALTH_SCRIPT)] + (extra_args or []))
    return _run_cached(cmd, timeout=30)


class TestHealthExitCode:
    def test_always_exits_zero_no_services(self):
        """Script must exit 0 even when all services are offline."""
        code, _, _ = run_health()
        assert code == 0, f"Expected exit 0, got {code}"

    def test_brief_flag_exits_zero(self):
        """--brief flag must also exit 0."""
        code, _, _ = run_health(["--brief"])
        assert code == 0, f"Expected exit 0 with --brief, got {code}"


class TestHealthJsonOutput:
    def test_stdout_is_valid_json(self):
        """Default output must be parseable JSON."""
        _, stdout, _ = run_health()
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout={stdout!r}")
        assert isinstance(data, dict)

    def test_top_level_status_key(self):
        """JSON must have a 'status' key with value 'ok' or 'degraded'."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert "status" in data, "Missing 'status' key"
        assert data["status"] in ("ok", "degraded"), (
            f"'status' must be 'ok' or 'degraded', got {data['status']!r}"
        )

    def test_top_level_services_key(self):
        """JSON must have a 'services' dict."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert "services" in data, "Missing 'services' key"
        assert isinstance(data["services"], dict), "'services' must be a dict"

    def test_services_has_rag(self):
        """services.rag must be present with required keys."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        rag = data["services"].get("rag")
        assert rag is not None, "Missing services.rag"
        assert "url" in rag, "services.rag missing 'url'"
        assert "available" in rag, "services.rag missing 'available'"
        assert "status" in rag, "services.rag missing 'status'"
        assert isinstance(rag["available"], bool)

    def test_services_has_clipboard(self):
        """services.clipboard must be present with required keys."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        clipboard = data["services"].get("clipboard")
        assert clipboard is not None, "Missing services.clipboard"
        assert "url" in clipboard, "services.clipboard missing 'url'"
        assert "available" in clipboard, "services.clipboard missing 'available'"
        assert "status" in clipboard, "services.clipboard missing 'status'"
        assert isinstance(clipboard["available"], bool)

    def test_top_level_local_data_key(self):
        """JSON must have a 'local_data' dict."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert "local_data" in data, "Missing 'local_data' key"
        ld = data["local_data"]
        assert isinstance(ld, dict), "'local_data' must be a dict"
        assert "schemas_dir" in ld, "local_data missing 'schemas_dir'"
        assert "available" in ld, "local_data missing 'available'"
        assert "plugins" in ld, "local_data missing 'plugins'"
        assert isinstance(ld["available"], bool)
        assert isinstance(ld["plugins"], int)

    def test_rag_url_contains_8765(self):
        """RAG URL should point at port 8765."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert "8765" in data["services"]["rag"]["url"]

    def test_clipboard_url_contains_8766(self):
        """Clipboard URL should point at port 8766."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert "8766" in data["services"]["clipboard"]["url"]

    def test_services_unavailable_without_live_services(self):
        """Both services should be unavailable (no live servers in test env)."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        # Services are offline in CI/test — both should report unavailable
        assert data["services"]["rag"]["available"] is False, (
            "RAG should be unavailable in test environment"
        )
        assert data["services"]["clipboard"]["available"] is False, (
            "Clipboard should be unavailable in test environment"
        )

    def test_status_is_degraded_without_live_services(self):
        """Status should be 'degraded' when services are offline."""
        _, stdout, _ = run_health()
        data = json.loads(stdout)
        assert data["status"] == "degraded", (
            f"Expected 'degraded' when services offline, got {data['status']!r}"
        )


class TestHealthBriefOutput:
    def test_brief_is_one_line(self):
        """--brief must produce a single non-empty line."""
        _, stdout, _ = run_health(["--brief"])
        lines = [l for l in stdout.splitlines() if l.strip()]
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {stdout!r}"

    def test_brief_format_contains_service_labels(self):
        """--brief line must contain RAG:, Clipboard:, Local: labels."""
        _, stdout, _ = run_health(["--brief"])
        line = stdout.strip()
        assert "RAG:" in line, f"Missing 'RAG:' in brief output: {line!r}"
        assert "Clipboard:" in line, f"Missing 'Clipboard:' in brief output: {line!r}"
        assert "Local:" in line, f"Missing 'Local:' in brief output: {line!r}"

    def test_brief_format_uses_plus_or_minus(self):
        """--brief symbols must be + or - for each service."""
        _, stdout, _ = run_health(["--brief"])
        line = stdout.strip()
        # Each label should be followed by + or -
        import re
        matches = re.findall(r"(?:RAG|Clipboard|Local):[+-]", line)
        assert len(matches) == 3, (
            f"Expected 3 'Label:[+-]' tokens, found {matches} in: {line!r}"
        )


# ---------------------------------------------------------------------------
# Task 2 — RAG HTTP bridge (rag.py)
# ---------------------------------------------------------------------------

RAG_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude/skills/construct3-copilot/scripts/query/rag.py"
)


def run_rag(extra_args=None, timeout=30):
    """Run rag.py and return (returncode, stdout, stderr). Results are cached."""
    cmd = tuple([sys.executable, str(RAG_SCRIPT)] + (extra_args or []))
    return _run_cached(cmd, timeout=timeout)


class TestRagBridge:
    def test_rag_offline_exits_nonzero(self):
        """When RAG is offline, rag.py exits 1 with error JSON."""
        # RAG is not running in test environment — connection should be refused
        code, stdout, _ = run_rag(["search", "collision detection"])
        assert code != 0, f"Expected non-zero exit when RAG is offline, got {code}"

    def test_rag_missing_query_exits_nonzero(self):
        """rag.py with no arguments exits 1."""
        code, stdout, _ = run_rag([])
        assert code != 0, f"Expected non-zero exit with no arguments, got {code}"

    def test_rag_output_is_valid_json(self):
        """Even on failure, rag.py outputs valid JSON."""
        # Test with offline service
        _, stdout, _ = run_rag(["search", "collision detection"])
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"stdout is not valid JSON on failure: {e}\nstdout={stdout!r}"
            )
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

    def test_rag_offline_error_has_suggestion(self):
        """Offline error JSON must include a 'suggestion' field."""
        _, stdout, _ = run_rag(["search", "collision detection"])
        data = json.loads(stdout)
        assert "error" in data, f"Missing 'error' key in: {data}"
        assert "suggestion" in data, f"Missing 'suggestion' key in: {data}"

    def test_rag_no_args_error_json(self):
        """No-argument error must be valid JSON with an 'error' key."""
        _, stdout, _ = run_rag([])
        data = json.loads(stdout)
        assert "error" in data, f"Missing 'error' key in: {data}"

    def test_rag_lookup_subcommand_offline(self):
        """lookup subcommand must also exit non-zero when RAG offline."""
        code, stdout, _ = run_rag(["lookup", "Sprite", "--plugin", "sprite"])
        assert code != 0
        data = json.loads(stdout)
        assert "error" in data

    def test_rag_verify_subcommand_offline(self):
        """verify subcommand (maps to lookup mode) must exit non-zero when RAG offline."""
        code, stdout, _ = run_rag(["verify", "set-animation", "--plugin", "sprite"])
        assert code != 0
        data = json.loads(stdout)
        assert "error" in data

    def test_rag_default_mode_auto(self):
        """Positional-only query (no subcommand) defaults to mode=auto, exits nonzero offline."""
        code, stdout, _ = run_rag(["fuzzy query here"])
        assert code != 0
        data = json.loads(stdout)
        assert "error" in data
