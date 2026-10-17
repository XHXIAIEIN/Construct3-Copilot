"""Verify the log endpoint reads only its allowlist, needs the page token, removes credentials and tails by offset."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from qqbot.model_manager import logs
from qqbot.model_manager.control import ModelControl
from qqbot.model_manager.server import create_server


class LogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name)
        (self.home / ".env").write_text(
            "QQ_APPID=10203040\nQQ_SECRET=qq-secret-value-1\nDEEPSEEK_API_KEY=sk-deepseek-123456\n"
            "C3BOT_API_KEY=ollama\nMY_PROVIDER=custom-provider-secret\nC3BOT_MODEL=deepseek-flash\n", encoding="utf-8")
        (self.home / "var").mkdir()
        (self.home / "var/apis.json").write_text(json.dumps({"profiles": [{"id": "x", "api_key_env": "MY_PROVIDER"}]}),
                                                 encoding="utf-8")
        self.bot = self.home / "var/logs/bot/bot.log"
        self.bot.parent.mkdir(parents=True)
        self.control = ModelControl(self.home)
        self.server = create_server(self.control, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        with urllib.request.urlopen(self.url, timeout=3) as response:
            self.token = response.read().decode().split('const token="', 1)[1].split('"', 1)[0]

    def get(self, path, token=None):
        request = urllib.request.Request(self.url + path, headers={"X-Panel-Token": self.token if token is None else token})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_logs_need_the_page_token(self):
        self.bot.write_text("2026-10-18 03:35:35,323 qqbot INFO hello\n", encoding="utf-8")
        for path in ("/api/logs", "/api/logs/bot"):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                self.get(path, token="")
            self.assertEqual(error.exception.code, 403)

    def test_only_listed_logs_can_be_read(self):
        catalog = self.get("/api/logs")["logs"]
        self.assertEqual([entry["id"] for entry in catalog], [entry[0] for entry in logs.LOGS])
        self.assertTrue(all("/" not in entry["file"] and "\\" not in entry["file"] for entry in catalog))
        for ident in ("..%2F..%2F.env", "../.env", "env", "bot%00"):
            with self.subTest(ident=ident), self.assertRaises(urllib.error.HTTPError) as error:
                self.get("/api/logs/" + ident)
            self.assertIn(error.exception.code, {400, 404})

    def test_known_credentials_are_hidden(self):
        self.bot.write_text(
            "2026-10-18 03:35:35,323 qqbot INFO token qq-secret-value-1 and sk-deepseek-123456\n"
            "2026-10-18 03:35:36,000 qqbot WARNING custom-provider-secret via ollama\n"
            "Authorization: Bearer abcdefghijklmnop\n", encoding="utf-8")
        text = "\n".join(self.get("/api/logs/bot")["lines"])
        for secret in ("qq-secret-value-1", "sk-deepseek-123456", "custom-provider-secret", "abcdefghijklmnop"):
            self.assertNotIn(secret, text)
        self.assertIn("‹已隐藏 QQ_SECRET›", text)
        self.assertIn("‹已隐藏 MY_PROVIDER›", text)
        # Short placeholders and public identifiers are not credentials.
        self.assertIn("via ollama", text)

    def test_tail_continues_from_offset_and_waits_for_whole_lines(self):
        self.bot.write_text("one\ntwo\n", encoding="utf-8")
        first = self.get("/api/logs/bot")
        self.assertEqual(first["lines"], ["one", "two"])
        with self.bot.open("a", encoding="utf-8") as stream:
            stream.write("three\nfou")
        second = self.get(f"/api/logs/bot?after={first['offset']}")
        self.assertEqual((second["lines"], second["reset"]), (["three"], False))
        with self.bot.open("a", encoding="utf-8") as stream:
            stream.write("r\n")
        self.assertEqual(self.get(f"/api/logs/bot?after={second['offset']}")["lines"], ["four"])
        self.bot.write_text("new file\n", encoding="utf-8")  # rotated: the old offset is past the end
        rotated = self.get(f"/api/logs/bot?after={second['offset'] + 50}")
        self.assertEqual((rotated["lines"], rotated["reset"]), (["new file"], True))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get("/api/logs/bot?after=x")
        self.assertEqual(error.exception.code, 400)

    def test_large_logs_are_capped(self):
        with self.bot.open("w", encoding="utf-8") as stream:
            for i in range(20000):
                stream.write(f"line {i:05d} " + "x" * 20 + "\n")
            stream.write("y" * 5000 + "\n")
        data = self.get("/api/logs/bot")
        self.assertTrue(data["clipped"])
        self.assertLessEqual(len(data["lines"]), logs.MAX_LINES)
        self.assertTrue(data["lines"][0].startswith("line "))
        self.assertLess(len(data["lines"][-1]), 1100)
        self.assertIn("截断", data["lines"][-1])

    def test_missing_log_reads_as_empty(self):
        data = self.get("/api/logs/usage")
        self.assertEqual((data["exists"], data["lines"]), (False, []))

    def test_usage_lists_qq_answers_without_openids(self):
        self.assertEqual(self.get("/api/usage"), {"clipped": False, "answers": [], "received": [], "sent": [], "builds": []})
        usage = self.home / "var/logs/bot/usage.log"
        usage.write_text("2026-10-16 21:00:39 query-fixed calls 5 prompt 15286 (cache hit 0) completion 388 in 42 s\n"
                         "2026-10-16 21:02:16 c2c_E5DB calls 20 prompt 164297 (cache hit 0) completion 3157 in 95 s\n"
                         "not a usage line\n"
                         "2026-10-16 22:00:00 group_G1_M2 calls 2 prompt 10 (cache hit 0) completion 5 in 3 s\n"
                         "2026-10-16 23:12:31 c2c_E5DB calls 39 prompt 1004162 (cache hit 0) completion 43496 in 1742 s\n",
                         encoding="utf-8")
        data = self.get("/api/usage")
        self.assertEqual([(a["at"], a["who"], a["seconds"]) for a in data["answers"]],
                         [("2026-10-16 21:02:16", 0, 95), ("2026-10-16 22:00:00", 1, 3), ("2026-10-16 23:12:31", 0, 1742)])
        self.assertEqual(data["answers"][0], {"at": "2026-10-16 21:02:16", "who": 0, "chat": "private", "calls": 20, "prompt": 164297,
                                              "completion": 3157, "seconds": 95})
        self.assertEqual(data["answers"][1]["chat"], "group")
        self.assertNotIn("E5DB", json.dumps(data))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get("/api/usage", token="")
        self.assertEqual(error.exception.code, 403)

    def test_project_events_come_from_bot_log(self):
        self.bot.write_text(
            "2026-10-16 20:59:51,230 copilot.construct3 INFO attachment: name-md5 a7ea, file, 680575 bytes, .zip\n"
            "2026-10-16 20:59:52,000 copilot.construct3 INFO attachment: name-md5 b8fb, image, 1200 bytes, .png\n"
            "2026-10-16 21:02:16,646 qqbot INFO group:G1:M2 tools: [\"presearch ['x']\", "
            "'new_project_from_spec({}) -> refused, nothing was built: / fixed: a / spec: bad', "
            "'patch_spec({\"a\": 1}) -> fixed: spec.objects[1].size: x / fixed: spec.objects[4].align: y / built: 2 object types', "
            "'print_sheet({})']\n"
            "2026-10-16 21:02:19,526 qqbot INFO sent file 74488 bytes\n"
            "2026-10-16 21:03:00,000 qqbot WARNING file send failed: timeout\n", encoding="utf-8")
        data = self.get("/api/usage")
        self.assertEqual(data["received"], [{"at": "2026-10-16 20:59:51", "bytes": 680575}])
        self.assertEqual(data["sent"], [{"at": "2026-10-16 21:02:19", "bytes": 74488, "ok": True},
                                        {"at": "2026-10-16 21:03:00", "bytes": 0, "ok": False}])
        self.assertEqual([(b["chat"], b["ok"], b["fixes"]) for b in data["builds"]], [("group", False, 0), ("group", True, 2)])
        self.assertNotIn("G1", json.dumps(data))


if __name__ == "__main__":
    unittest.main()
