"""
Contract tests for rag.py against a stand-in for the Construct3-RAG lookup service.

The stand-in applies the request contract of POST /search the way the service
does: a field or a value outside the contract is answered with HTTP 422. Every
request is recorded, so a test can assert both what rag.py sent and that the
service would have accepted it.

rag.py is imported and called in-process: no child processes, which keeps this
file clear of the Windows handle limit described in test_service_integration.py.
"""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RAG_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude/plugins/construct3-copilot/scripts/query/rag.py"
)

# The request contract of the lookup-only service (docs/guide/api-reference.md
# in Construct3-RAG). Unknown fields are forbidden.
ALLOWED_VALUES = {
    "mode": {"auto", "lookup", "list"},
    "scope": {"eventsheet", "scripts", "js", "ts", "all"},
    "lang": {"en", "zh", "ja", "ko"},
}
ALLOWED_FIELDS = {"query", "debug", "context", *ALLOWED_VALUES}


def _ace(ace_id: str) -> dict:
    return {"ace_id": ace_id, "name": {"en": {"name": ace_id}}, "is_trigger": False, "is_async": False}


# What a bare-addon lookup returns, keyed by the lowercased query.
ADDONS = {
    "sprite": {"sprite": {"actions": [_ace("set-animation-frame"), _ace("set-animation")]},
               "_common": {"actions": [_ace("set-angle"), _ace("toggle-boolean-instvar")]}},
    "system": {"system": {"actions": [_ace("toggle-boolean-eventvar")], "conditions": [_ace("for")]}},
    "keyboard": {"keyboard": {"conditions": [_ace("key-is-down")]}},
    "tween": {"tween": {"actions": [_ace("tween-one-property")]}},
    "advancedrandom": {"advancedrandom": {"actions": [_ace("seed")], "expressions": [_ace("seed")]}},
    "_common": {"_common": {"actions": [_ace("set-angle"), _ace("toggle-boolean-instvar")]}},
    # A behavior without ACEs: the service answers with a scripting API instead.
    "destroy": {"IInstance": {"script_apis": [_ace("destroy")]}},
}


def _violations(body: dict) -> list[str]:
    problems = [f"body.{field}: Extra inputs are not permitted" for field in body if field not in ALLOWED_FIELDS]
    for field, allowed in ALLOWED_VALUES.items():
        if field in body and body[field] not in allowed:
            problems.append(f"body.{field}: Input should be one of {sorted(allowed)}")
    query = body.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        problems.append("body.query: must be 1 to 500 characters")
    return problems


class _StandIn(BaseHTTPRequestHandler):
    requests: list[tuple[int, dict]] = []

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        problems = _violations(body)
        if problems:
            status = 422
            payload = {"detail": [{"loc": p.split(":")[0].split("."), "msg": p.split(": ", 1)[1]} for p in problems]}
        else:
            status = 200
            payload = {"query": body["query"], "lang": body.get("lang", "en"), "mode": body.get("mode", "auto"), "ms": 0.1}
            matches = ADDONS.get(body["query"].strip().lower())
            if matches and payload["mode"] == "list":
                payload["lookup"] = {
                    ace_type: [item["name"]["en"]["name"] for item in items]
                    for groups in matches.values()
                    for ace_type, items in groups.items()
                }
            elif matches:
                payload["lookup"] = {"matches": matches}
        _StandIn.requests.append((status, body))
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args) -> None:  # keep pytest output quiet
        pass


@pytest.fixture(scope="module")
def service_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/search"
    server.shutdown()
    server.server_close()


@pytest.fixture
def rag(service_url, monkeypatch):
    spec = importlib.util.spec_from_file_location("rag", RAG_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "RAG_URL", service_url)
    _StandIn.requests.clear()
    return module


def run(rag, argv: list[str]) -> tuple[int, dict]:
    exit_code, output = rag._parse_args(argv)
    return exit_code, json.loads(output)


class TestRequestsStayInsideTheContract:
    @pytest.mark.parametrize(
        "argv",
        [
            ["search", "Sprite collision"],
            ["lookup", "Sprite collision", "--lang", "zh"],
            ["lookup", "Platform jump", "--scope", "scripts"],
            ["list", "Sprite"],
            ["Sprite collision"],
            ["search", "how to make an enemy patrol"],
            ["verify", "sprite:set-animation"],
            ["verify", "sprite:set-angle", "--lang", "zh", "--scope", "all"],
            ["verify", "nosuchaddon:set-animation"],
        ],
    )
    def test_every_request_is_accepted(self, rag, argv):
        run(rag, argv)
        assert _StandIn.requests, "rag.py sent nothing"
        rejected = [body for status, body in _StandIn.requests if status != 200]
        assert not rejected, f"the service would answer 422 to: {rejected}"

    @pytest.mark.parametrize(
        ("argv", "mode"),
        [
            (["search", "Sprite collision"], "auto"),
            (["Sprite collision"], "auto"),
            (["lookup", "Sprite collision"], "lookup"),
            (["list", "Sprite"], "list"),
            (["verify", "sprite:set-animation"], "lookup"),
        ],
    )
    def test_subcommand_sets_the_mode(self, rag, argv, mode):
        run(rag, argv)
        assert {body["mode"] for _, body in _StandIn.requests} == {mode}

    @pytest.mark.parametrize(
        "argv",
        [
            ["semantic", "enemy patrol"],
            ["search", "move", "--top-k", "5"],
            ["search", "addon SDK plugin", "--collections", "addon_sdk"],
            ["lookup", "on-click", "--plugin", "mouse"],
            ["verify", "set-animation", "--plugin", "sprite"],
            ["lookup", "Sprite", "--scope", "bogus"],
            ["lookup", "Sprite", "--lang", "fr"],
            ["lookup", "Sprite", "--scope"],
            ["lookup", "x" * 501],
            ["verify", "set-animation"],
        ],
    )
    def test_what_the_service_cannot_honor_fails_before_any_request(self, rag, argv):
        exit_code, data = run(rag, argv)
        assert exit_code == 1
        assert "error" in data
        assert _StandIn.requests == []

    def test_plugin_flag_names_the_replacement_command(self, rag):
        _, data = run(rag, ["verify", "set-animation", "--plugin", "sprite"])
        assert "rag.py verify sprite:set-animation" in data["suggestion"]


class TestVerify:
    def test_exact_id_is_verified(self, rag):
        exit_code, data = run(rag, ["verify", "sprite:set-animation"])
        assert exit_code == 0
        assert data["verified"] is True
        assert [(m["addon"], m["ace_type"], m["ace_id"]) for m in data["matches"]] == [
            ("sprite", "actions", "set-animation")
        ]

    def test_id_contained_in_a_real_id_is_not_verified(self, rag):
        """toggle-boolean is text inside toggle-boolean-eventvar, not an ACE ID."""
        exit_code, data = run(rag, ["verify", "system:toggle-boolean"])
        assert exit_code == 1
        assert data["verified"] is False
        assert data["nearest"][0] == "system:toggle-boolean-eventvar"

    def test_common_ace_is_verified_with_a_note(self, rag):
        exit_code, data = run(rag, ["verify", "sprite:set-angle"])
        assert exit_code == 0
        assert data["matches"][0]["addon"] == "_common"
        assert "common ACE" in data["note"]

    @pytest.mark.parametrize("addon", ["system", "keyboard", "tween"])
    def test_common_ace_requires_membership_in_the_addon_schema(self, rag, addon):
        exit_code, data = run(rag, ["verify", f"{addon}:set-angle"])
        assert exit_code == 1 and data["verified"] is False
        assert len(_StandIn.requests) == 1

    def test_common_addon_is_asked_once(self, rag):
        exit_code, _ = run(rag, ["verify", "_common:no-such-ace"])
        assert exit_code == 1
        assert len(_StandIn.requests) == 1

    def test_id_under_two_ace_types_returns_both(self, rag):
        _, data = run(rag, ["verify", "advancedrandom:seed"])
        assert [m["ace_type"] for m in data["matches"]] == ["actions", "expressions"]

    def test_unknown_addon_is_reported_as_such(self, rag):
        exit_code, data = run(rag, ["verify", "nosuchaddon:set-animation"])
        assert exit_code == 1
        assert "not recognized" in data["error"]

    def test_unknown_addon_does_not_verify_a_common_ace(self, rag):
        exit_code, data = run(rag, ["verify", "nosuchaddon:set-angle"])
        assert exit_code == 1
        assert data["verified"] is False
        assert "not recognized" in data["error"]
        assert len(_StandIn.requests) == 1

    def test_scripting_api_hit_is_not_an_ace(self, rag):
        exit_code, data = run(rag, ["verify", "destroy:destroy"])
        assert exit_code == 1
        assert data["verified"] is False


class TestServiceAnswers:
    def test_error_status_is_not_reported_as_offline(self, rag):
        exit_code, output = rag._call_rag({"query": "x", "mode": "semantic"})
        error = json.loads(output)["error"]
        assert exit_code == 1
        assert "HTTP 422" in error and "body.mode" in error
        assert "offline" not in error

    def test_answer_without_lookup_section_is_passed_through_with_a_hint(self, rag, capsys):
        exit_code, data = run(rag, ["search", "how to make an enemy patrol"])
        assert exit_code == 0
        assert "lookup" not in data
        assert "no lookup section" in capsys.readouterr().err

    def test_answer_with_lookup_section_has_no_hint(self, rag, capsys):
        run(rag, ["lookup", "Sprite"])
        assert capsys.readouterr().err == ""
