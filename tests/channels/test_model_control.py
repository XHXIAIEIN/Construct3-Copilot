"""Offline checks for local model selection and bounded gateway replacement."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock, patch

from channels.panel.control import ControlError, ModelControl


class ModelControlTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / ".tmp" / "model-control-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / "qq").mkdir(parents=True)
        (self.home / "qq" / "bot.py").write_text("", encoding="utf-8")
        self.original = (b"# configuration\nQQ_SECRET=private-placeholder\nKEEP=yes\nC3BOT_MODEL=old-model\n"
                         b"C3BOT_BASE_URL=http://127.0.0.1:11434/v1\nC3BOT_API_KEY=old-placeholder\n"
                         b"C3BOT_EXTRA_BODY='{\n  \"thinking\": true\n}'\n")
        (self.home / ".env").write_bytes(self.original)
        self.control = ModelControl(self.home, repo=self.home)
        self.config = {"url": "http://127.0.0.1:11434", "executable": str(self.home / "ollama.exe"), "models_dir": str(self.home / "models")}
        self.control.config_path.parent.mkdir()
        self.control.config_path.write_text(json.dumps({"ollama": self.config}), encoding="utf-8")
        self.receipt = {"pid": 200, "status": "ready", "started_at": "2026-01-01T00:00:01Z", "ready_at": "2026-01-01T00:00:02Z"}
        receipt_path = self.home / "var" / "runtime" / "gateway.json"
        receipt_path.parent.mkdir()
        receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")
        self.process = {"ProcessId": 200, "ParentProcessId": 100, "ExecutablePath": str(self.home / "shared-python.exe"),
                        "CommandLine": f'"{self.home / "shared-python.exe"}" -u bot.py', "created_at": "2026-01-01T00:00:00.100Z"}
        self.parent = {"ProcessId": 100, "ParentProcessId": 1, "ExecutablePath": str(self.control.python),
                       "CommandLine": f'"{self.control.python}" -u bot.py', "created_at": "2026-01-01T00:00:00Z"}

    def api(self, config, path, payload=None, timeout=3):
        if path == "/api/tags":
            return {"models": [{"name": "example:small", "size": 123, "details": {"parameter_size": "1B", "quantization_level": "Q4"}, "digest": "not-returned"}]}
        if path == "/api/ps":
            return {"models": [{"name": "example:small"}]}
        if path == "/api/show":
            return {"capabilities": ["completion", "tools"]}
        if path == "/api/generate":
            return {"done": True}
        raise AssertionError(path)

    def prepare_switch(self):
        patches = [patch.object(self.control, "_request", side_effect=self.api),
                   patch.object(self.control, "_gateway_identity", return_value=[self.process, self.parent]),
                   patch.object(self.control, "_stop"), patch.object(self.control, "_stop_launched"),
                   patch.object(self.control, "_launch_bot", return_value=SimpleNamespace(pid=300)),
                   patch.object(self.control, "_wait_ready", return_value={"pid": 300}),
                   patch.object(self.control, "status", return_value={"current": {"model": "example:small"}})]
        mocks = [p.start() for p in patches]
        for item in patches:
            self.addCleanup(item.stop)
        return mocks

    def test_status_only_returns_public_fields(self):
        with patch.object(self.control, "_request", side_effect=self.api), patch.object(self.control, "_process", return_value=None):
            status = self.control.status()
        self.assertTrue(status["ollama"]["online"])
        self.assertTrue(status["models"][0]["loaded"])
        self.assertFalse(status["gateway"]["alive"])
        serialized = json.dumps(status)
        for private in ("private-placeholder", "old-placeholder", "digest", "QQ_SECRET"):
            self.assertNotIn(private, serialized)

    def test_parent_exit_after_child_stop_is_success(self):
        with patch.object(self.control, "_process", side_effect=[self.process, self.parent, None]), \
             patch("channels.panel.control.subprocess.run", side_effect=[
                 subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)
             ]) as stop:
            self.control._stop([self.process, self.parent])
        self.assertEqual(stop.call_count, 2)

    def test_api_switch_uses_key_reference_and_preserves_unrelated_settings(self):
        self.prepare_switch()
        result = self.control.switch("remote-placeholder", api={"id": "example", "model": "remote-placeholder",
            "base_url": "https://example.test/v1", "api_key_env": "PROVIDER_KEY", "protocol": "anthropic"})
        self.assertTrue(result["ok"], result)
        values = self.control._env()
        self.assertEqual(values["C3BOT_BASE_URL"], "https://example.test/v1")
        self.assertEqual(values["C3BOT_API_KEY_ENV"], "PROVIDER_KEY")
        self.assertEqual(values["C3BOT_API_PROTOCOL"], "anthropic")
        local = self.control._updated_env(self.control.env_path.read_bytes(), self.config, "example:small")
        self.assertNotIn(b"C3BOT_API_PROTOCOL", local)
        self.assertNotIn("C3BOT_API_KEY", values)
        self.assertEqual(values["QQ_SECRET"], "private-placeholder")

    def test_stop_failure_keeps_a_live_process_as_failure(self):
        with patch.object(self.control, "_process", return_value=self.parent), \
             patch("channels.panel.control.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(ControlError):
                self.control._stop([self.parent])

    def test_configuration_is_read_again_per_operation(self):
        self.assertEqual(self.control._config()["url"], self.config["url"])
        self.config["url"] = "http://127.0.0.1:12345"
        self.control.config_path.write_text(json.dumps({"ollama": self.config}), encoding="utf-8")
        self.assertEqual(self.control._config()["url"], self.config["url"])

    def test_registry_models_directory_overrides_stale_process_environment(self):
        self.control.config_path.unlink()
        with patch("channels.panel.control._registry_models", return_value="registry-models"), patch.dict(os.environ, {"OLLAMA_MODELS": "stale-models"}):
            self.assertEqual(self.control._config()["models_dir"], "registry-models")

    def test_remote_or_credentialed_service_urls_are_refused(self):
        for value in ("http://example.test:11434", "http://user:secret@localhost:11434", "http://127.0.0.1:11434?token=secret"):
            with self.subTest(value=value), self.assertRaises(ControlError):
                self.control._local_url(value)

    def test_warm_never_pulls_and_requires_installed_tool_capability(self):
        with patch.object(self.control, "_request", side_effect=self.api) as request, patch.object(self.control, "status", return_value={}):
            result = self.control.warm("example:small")
        self.assertTrue(result["ok"])
        generate = [c for c in request.call_args_list if c.args[1] == "/api/generate"]
        self.assertEqual(generate[0].args[2], {"model": "example:small", "stream": False, "keep_alive": "10m"})
        self.assertFalse(any(c.args[1] == "/api/pull" for c in request.call_args_list))

    def test_embedding_only_model_is_not_loaded(self):
        def embedding(config, path, payload=None, timeout=3):
            return {"capabilities": ["embedding"]} if path == "/api/show" else self.api(config, path, payload, timeout)
        with patch.object(self.control, "_request", side_effect=embedding) as request:
            self.assertFalse(self.control.warm("example:small")["ok"])
        self.assertFalse(any(c.args[1] == "/api/generate" for c in request.call_args_list))

    def test_switch_updates_only_managed_bindings_and_keeps_backup(self):
        mocks = self.prepare_switch()
        result = self.control.switch("example:small")
        self.assertTrue(result["ok"])
        changed = (self.home / ".env").read_text(encoding="utf-8")
        self.assertIn("QQ_SECRET=private-placeholder\nKEEP=yes\n", changed)
        self.assertIn("C3BOT_MODEL=example:small\n", changed)
        self.assertIn("C3BOT_API_KEY=ollama\nC3BOT_REASONING=none\n", changed)
        self.assertNotIn("C3BOT_EXTRA_BODY", changed)
        self.assertNotIn('"thinking"', changed)
        self.assertEqual(next((self.home / "var" / "backups" / "models").glob("*.env")).read_bytes(), self.original)
        mocks[2].assert_called_once_with([self.process, self.parent])

    def test_unknown_gateway_identity_leaves_configuration_and_processes(self):
        mocks = self.prepare_switch()
        mocks[1].side_effect = ControlError("identity mismatch")
        result = self.control.switch("example:small")
        self.assertFalse(result["ok"])
        self.assertEqual((self.home / ".env").read_bytes(), self.original)
        mocks[2].assert_not_called()
        mocks[4].assert_not_called()

    def test_absent_receipt_allows_a_fresh_gateway_when_no_candidate_exists(self):
        mocks = self.prepare_switch()
        with patch.object(self.control, "_receipt", return_value={}), patch.object(self.control, "_gateway_candidates", return_value=[]):
            result = self.control.switch("example:small")
        self.assertTrue(result["ok"])
        mocks[2].assert_called_once_with([])
        mocks[4].assert_called_once()

    def test_absent_receipt_refuses_an_existing_unknown_gateway(self):
        mocks = self.prepare_switch()
        with patch.object(self.control, "_receipt", return_value={}), patch.object(self.control, "_gateway_candidates", return_value=[self.parent]):
            self.assertFalse(self.control.switch("example:small")["ok"])
        self.assertEqual((self.home / ".env").read_bytes(), self.original)
        mocks[2].assert_not_called()

    def test_failed_launch_cleanup_checks_direct_children_before_stopping(self):
        launched = SimpleNamespace(pid=100, _control_started_at="2025-12-31T23:59:59.999Z")
        with patch.object(self.control, "_process", return_value=self.parent), patch.object(self.control, "_children", return_value=[self.process]), patch.object(self.control, "_stop") as stop:
            self.control._stop_launched(launched)
        stop.assert_called_once_with([self.process, self.parent])
        changed = {**self.process, "CommandLine": 'python.exe unrelated.py'}
        with patch.object(self.control, "_process", return_value=self.parent), patch.object(self.control, "_children", return_value=[changed]), patch.object(self.control, "_stop") as stop:
            with self.assertRaises(ControlError):
                self.control._stop_launched(launched)
        stop.assert_not_called()

    def test_running_conversation_refuses_switch_before_configuration_write(self):
        mocks = self.prepare_switch()
        database = self.home / "var" / "copilot" / "tasks.sqlite3"
        database.parent.mkdir()
        with closing(sqlite3.connect(database)) as db:
            db.execute("CREATE TABLE tasks (capability TEXT,status TEXT)")
            db.execute("INSERT INTO tasks VALUES ('conversation','running')")
            db.commit()
        self.assertFalse(self.control.switch("example:small")["ok"])
        self.assertEqual((self.home / ".env").read_bytes(), self.original)
        mocks[2].assert_not_called()

    def test_startup_failure_rolls_back_only_its_own_config(self):
        mocks = self.prepare_switch()
        mocks[1].side_effect = [[self.process, self.parent], []]
        mocks[5].side_effect = [ControlError("ready timeout"), {"pid": 301}]
        result = self.control.switch("example:small")
        self.assertFalse(result["ok"])
        self.assertEqual((self.home / ".env").read_bytes(), self.original)
        self.assertEqual(mocks[4].call_count, 2)

    def test_startup_failure_preserves_later_user_configuration(self):
        mocks = self.prepare_switch()
        later = self.original + b"CUSTOM=retained\n"
        def changed(*args):
            (self.home / ".env").write_bytes(later)
            raise ControlError("ready timeout")
        mocks[5].side_effect = changed
        self.assertFalse(self.control.switch("example:small")["ok"])
        self.assertEqual((self.home / ".env").read_bytes(), later)
        mocks[3].assert_not_called()

    def test_legacy_child_requires_trusted_parent_and_matching_creation_time(self):
        with patch.object(self.control, "_process", side_effect=lambda pid: {200: self.process, 100: self.parent}.get(pid)):
            self.assertEqual(len(self.control._gateway_identity(self.receipt)), 2)
            self.receipt["started_at"] = "2026-01-01T01:00:00Z"
            with self.assertRaises(ControlError):
                self.control._gateway_identity(self.receipt)

    def test_module_launcher_is_accepted_and_cli_mode_is_refused(self):
        self.parent["CommandLine"] = f'"{self.control.python}" -u -m channels.qq'
        self.assertTrue(self.control._bot_command(self.parent))
        self.parent["CommandLine"] += ' --cli "placeholder"'
        self.assertFalse(self.control._bot_command(self.parent))

    def test_reused_pid_is_not_stopped(self):
        altered = {**self.process, "created_at": "2026-01-02T00:00:00Z"}
        with patch.object(self.control, "_process", return_value=altered), patch("channels.panel.control.subprocess.run") as run:
            with self.assertRaises(ControlError):
                self.control._stop([self.process])
        run.assert_not_called()

    def test_bot_launch_is_fixed_module_and_drops_inherited_managed_environment(self):
        self.control.python.parent.mkdir(parents=True)
        self.control.python.write_bytes(b"placeholder")
        with patch.dict(os.environ, {"C3BOT_EXTRA_BODY": "stale", "C3BOT_MODEL": "stale", "QQ_SECRET": "stale"}), patch.object(self.control, "_detached") as detached:
            self.control._launch_bot()
        argv, env = detached.call_args.args[:2]
        self.assertEqual(argv, [str(self.control.python), "-u", "-m", "channels.qq"])
        self.assertNotIn("C3BOT_MODEL", env)
        self.assertNotIn("C3BOT_EXTRA_BODY", env)
        self.assertNotIn("QQ_SECRET", env)

    def test_ready_receipt_must_be_fresh_and_match_launched_process(self):
        self.control.READY_TIMEOUT = .01
        with patch.object(self.control, "_receipt", return_value=self.receipt), patch.object(self.control, "_gateway_identity") as identity, patch("channels.panel.control.time.sleep"):
            with self.assertRaises(ControlError):
                self.control._wait_ready(SimpleNamespace(pid=300, poll=lambda: None), "2026-01-02T00:00:00Z")
        identity.assert_not_called()


if __name__ == "__main__":
    unittest.main()
