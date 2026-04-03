"""
Integration tests for health.py service discovery script.

Tests run without live services — all service probes are expected to fail/timeout,
and the script must still exit 0 with valid JSON output.
"""

import json
import subprocess
import sys
from pathlib import Path

HEALTH_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude/skills/construct3-copilot/scripts/infra/health.py"
)


def run_health(extra_args=None):
    """Run health.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(HEALTH_SCRIPT)] + (extra_args or [])
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
    )
    return result.returncode, result.stdout, result.stderr


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
