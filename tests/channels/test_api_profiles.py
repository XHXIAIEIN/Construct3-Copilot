"""Verify API credentials, recoverable management and balance evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from channels.panel.control import ControlError, ModelControl
from channels.panel.api_profiles import ApiProfiles, api_url


class ApiProfileTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / ".tmp" / "api-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / ".env").write_text('QQ_SECRET="private-placeholder"\nDEEPSEEK_API_KEY="key-placeholder"\n', encoding="utf-8")
        self.control = ModelControl(self.home)
        self.registry = ApiProfiles(self.control)

    def test_existing_keys_are_imported_as_references_without_disclosure(self):
        profiles = self.registry.public()
        self.assertEqual(profiles[0]["name"], "DeepSeek")
        self.assertTrue(profiles[0]["has_key"])
        for data in (json.dumps(profiles), self.registry.path.read_text()):
            self.assertNotIn("key-placeholder", data)
            self.assertNotIn("private-placeholder", data)

    def test_add_edit_delete_and_restart_keep_secret_private_and_backup(self):
        self.registry.save({"id": "example", "name": "Example", "model": "example-model",
                            "base_url": "https://example.test/v1", "api_key": "new-placeholder"})
        self.assertEqual(self.control.env()["QQBOT_API_EXAMPLE"], "new-placeholder")
        self.registry.save({"id": "example", "name": "Edited", "model": "example-model",
                            "base_url": "https://example.test/v1", "balance_mark": "low"})
        self.assertEqual(self.registry.public()[-1]["balance_mark"], "low")
        self.registry.delete("example")
        self.assertEqual([p["id"] for p in ApiProfiles(self.control).public()], ["deepseek"])
        self.assertTrue(list((self.home / "var/backups/apis").glob("*.json")))
        self.assertEqual(self.control.env()["QQ_SECRET"], "private-placeholder")
        self.assertEqual(self.control.env()["QQBOT_API_EXAMPLE"], "new-placeholder")

    def test_deleted_import_is_not_reimported(self):
        self.registry.public()
        self.registry.delete("deepseek")
        self.assertEqual(ApiProfiles(self.control).public(), [])

    def test_current_profile_cannot_be_deleted_or_edited(self):
        self.registry.public()
        with (self.home / ".env").open("a") as stream:
            stream.write("C3BOT_API_PROFILE=deepseek\n")
        with self.assertRaises(ControlError):
            self.registry.delete("deepseek")
        with self.assertRaises(ControlError):
            self.registry.save({"id": "deepseek", "name": "Changed"})

    def test_balance_keeps_currency_availability_and_query_time(self):
        with patch("channels.panel.api_profiles.fetch_json", return_value={
            "is_available": False, "balance_infos": [{"currency": "CNY", "total_balance": "0.00"}]
        }):
            self.registry.balance("deepseek")
        balance = self.registry.public()[0]["balance"]
        self.assertEqual(balance["state"], "unavailable")
        self.assertEqual(balance["entries"], [{"currency": "CNY", "amount": "0.00"}])
        self.assertTrue(balance["checked_at"])

    def test_balance_failure_is_unknown_amount_not_zero(self):
        with patch("channels.panel.api_profiles.fetch_json", side_effect=ControlError("offline")):
            self.registry.balance("deepseek")
        balance = self.registry.public()[0]["balance"]
        self.assertEqual(balance["state"], "error")
        self.assertNotIn("entries", balance)

    def test_manual_balance_does_not_send_a_network_request(self):
        self.registry.save({"id": "example", "name": "Example", "model": "example-model",
                            "base_url": "https://example.test/v1", "balance_mark": "empty"})
        with patch("channels.panel.api_profiles.fetch_json") as fetch:
            self.registry.balance("example")
        fetch.assert_not_called()
        self.assertEqual(self.registry.public()[-1]["balance"]["state"], "unsupported")

    def test_misnamed_key_variable_is_explained_and_can_be_repointed(self):
        with (self.home / ".env").open("a") as stream:
            stream.write('BIGMODEL_KEY="zhipu-placeholder"\n')
        self.registry.public()
        self.registry.save({"id": "zhipu", "name": "智谱", "model": "glm-4.5-flash",
                            "base_url": "https://open.bigmodel.cn/api/anthropic", "protocol": "anthropic"})
        data = json.loads(self.registry.path.read_text(encoding="utf-8"))
        next(p for p in data["profiles"] if p["id"] == "zhipu")["api_key_env"] = "ZHIPU_API_KEY"
        self.registry.path.write_text(json.dumps(data), encoding="utf-8")
        zhipu = next(p for p in self.registry.public() if p["id"] == "zhipu")
        self.assertEqual((zhipu["has_key"], zhipu["api_key_env"], zhipu["key_alternatives"]),
                         (False, "ZHIPU_API_KEY", ["BIGMODEL_KEY"]))
        self.assertEqual(zhipu["effective_protocol"], "anthropic")
        self.assertEqual(self.registry.key_names(), ["BIGMODEL_KEY", "DEEPSEEK_API_KEY"])
        self.registry.save({"id": "zhipu", "name": "智谱", "model": "glm-4.5-flash", "protocol": "anthropic",
                            "base_url": "https://open.bigmodel.cn/api/anthropic", "api_key_env": "BIGMODEL_KEY"})
        zhipu = next(p for p in self.registry.public() if p["id"] == "zhipu")
        self.assertTrue(zhipu["ready"])
        self.assertNotIn("zhipu-placeholder", json.dumps(self.registry.public()) + self.registry.path.read_text(encoding="utf-8"))

    def test_key_variable_must_exist_and_cannot_borrow_reserved_names(self):
        for name in ("MISSING_KEY", "QQ_SECRET", "C3BOT_API_KEY", "bad name"):
            with self.subTest(name=name), self.assertRaises(ControlError):
                self.registry.save({"id": "example", "name": "Example", "api_key_env": name})

    def test_auto_protocol_resolves_like_the_bot(self):
        self.registry.save({"id": "claude", "name": "Claude", "base_url": "https://api.anthropic.com/v1"})
        self.registry.save({"id": "other", "name": "Other", "base_url": "https://example.test/api/anthropic"})
        profiles = {p["id"]: p for p in self.registry.public()}
        self.assertEqual(profiles["claude"]["effective_protocol"], "anthropic")
        self.assertEqual((profiles["other"]["protocol"], profiles["other"]["effective_protocol"]), ("auto", "openai"))

    def test_urls_reject_credentials_and_nonlocal_plaintext(self):
        for url in ("http://example.test/v1", "https://user:password@example.test/v1", "https://example.test/v1?key=example"):
            with self.subTest(url=url), self.assertRaises(ControlError):
                api_url(url)
