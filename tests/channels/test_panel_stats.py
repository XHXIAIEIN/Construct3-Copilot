"""Verify the panel's atomic statistics, the base metrics, the application's declared ones, and the fallback without
a declaration. Records here are written as a channel writes them; the panel knows no application."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from channels.core.answers import AnswerLog
from channels.panel import stats
from channels.panel.control import ModelControl
from channels.panel.server import create_server

RECORDS = [
    {"chat": "private", "session": "c2c:A", "seconds": 10, "prompt": 100, "completion": 10, "ok": True,
     "files_in": [{"type": ".c3p", "bytes": 1000}], "files_out": [{"type": ".c3p", "bytes": 500, "sent": True}],
     "app": {"build": "ok", "fixes": 2, "tools": [{"name": "lookup_ace", "ok": False}, {"name": "ace-check", "ok": True}]}},
    {"chat": "group", "session": "group:G:M", "seconds": 30, "prompt": 50, "completion": 5, "ok": False,
     "files_in": [], "files_out": [{"type": ".c3p", "bytes": 300, "sent": False}],
     "app": {"build": "failed", "fixes": 1, "tools": [{"name": "lookup_ace", "ok": True}, {"name": "patch_spec", "ok": False}]}},
    {"chat": "private", "session": "c2c:A", "seconds": 20, "prompt": 10, "completion": 1, "ok": True,
     "files_in": [], "files_out": []},  # no record from the application
]


class AtomTests(unittest.TestCase):
    def test_count_sum_avg_rate(self):
        self.assertEqual(stats.evaluate({"op": "count"}, RECORDS), 3)
        self.assertEqual(stats.evaluate({"op": "count", "distinct": "session"}, RECORDS), 2)
        self.assertEqual(stats.evaluate({"op": "sum", "field": "prompt"}, RECORDS), 160)
        self.assertEqual(stats.evaluate({"op": "sum", "field": ["prompt", "completion"]}, RECORDS), 176)
        self.assertEqual(stats.evaluate({"op": "avg", "field": "seconds"}, RECORDS), 20)
        self.assertAlmostEqual(stats.evaluate({"op": "rate", "field": "ok"}, RECORDS), 2 / 3)
        self.assertEqual(stats.evaluate({"op": "sum", "field": "app.fixes"}, RECORDS), 3)  # a missing field adds nothing
        self.assertIsNone(stats.evaluate({"op": "avg", "field": "seconds"}, []))
        self.assertIsNone(stats.evaluate({"op": "rate", "field": "ok"}, []))
        with self.assertRaises(ValueError):
            stats.evaluate({"op": "median", "field": "seconds"}, RECORDS)

    def test_where_each_by_split(self):
        self.assertEqual(stats.evaluate({"op": "count", "where": {"chat": "private"}}, RECORDS), 2)
        self.assertEqual(stats.evaluate({"op": "count", "where": {"app.build": ["ok", "failed"]}}, RECORDS), 2)
        self.assertEqual(stats.evaluate({"op": "count", "each": "files_out", "where": {"sent": True}}, RECORDS), 1)
        self.assertEqual(stats.evaluate({"op": "sum", "each": "files_in", "field": "bytes"}, RECORDS), 1000)
        self.assertEqual(stats.evaluate({"op": "count", "by": "app.build"}, RECORDS), {"ok": 1, "failed": 1})
        self.assertEqual(stats.evaluate({"op": "count", "split": "ok"}, RECORDS), {"true": 2, "false": 1})
        self.assertEqual(stats.evaluate({"op": "count", "each": "app.tools", "by": "name", "split": "ok"}, RECORDS),
                         {"lookup_ace": {"true": 1, "false": 1}, "ace-check": {"true": 1, "false": 0},
                          "patch_spec": {"true": 0, "false": 1}})

    def test_scalar_adds_parts_only_where_the_op_adds_up(self):
        count = {"op": "count", "by": "app.build"}
        self.assertEqual(stats.scalar(count, stats.evaluate(count, RECORDS)), 2)
        self.assertIsNone(stats.scalar({"op": "avg"}, {"a": 1, "b": 2}))
        self.assertTrue(stats.additive(count))
        self.assertFalse(stats.additive({"op": "count", "distinct": "session"}))
        self.assertFalse(stats.additive({"op": "avg"}))


class ReportTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".tmp" / "stats-tests"
        root.mkdir(parents=True, exist_ok=True)
        folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name)
        self.data = self.home / "var"
        self.now = datetime(2026, 10, 18, 15, 0, tzinfo=timezone(timedelta(hours=8)))
        lines = []
        for i, record in enumerate(RECORDS):
            at = (self.now - timedelta(days=i)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            lines.append(json.dumps({"at": at, "channel": "qq", **record}))
        lines.append("{torn line")
        lines.append(json.dumps({"at": "2025-01-01T00:00:00Z", "chat": "private", "session": "old", "ok": True}))
        answers = self.data / "logs" / "qq" / "answers.jsonl"
        answers.parent.mkdir(parents=True)
        answers.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def describe(self, description):
        path = self.data / "runtime" / "app.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(description), encoding="utf-8")

    def test_without_a_declaration_only_base_metrics_show(self):
        report = stats.report(self.data, "day", self.now)
        self.assertIsNone(report["app"])
        self.assertEqual(report["app_note"], stats.NO_APP)
        self.assertEqual((report["total"], report["count"], report["since"]), (4, 3, "2025-01-01"))
        base = {m["id"]: m for m in report["base"]}
        self.assertEqual([m["id"] for m in report["base"]], [m["id"] for m in stats.BASE])
        self.assertEqual((base["answers"]["value"], base["people"]["value"], base["tokens"]["value"]), (3, 2, 176))
        self.assertAlmostEqual(base["answers"]["note"]["value"], 2 / 3)
        self.assertEqual((base["sent"]["value"], base["sent"]["note"]["value"]), (1, 1))
        # one column a day, private / group / other stacked; today is the last
        self.assertEqual(len(report["buckets"]), 14)
        self.assertEqual(base["answers"]["trend"][-3:], [[1, 0, 0], [0, 1, 0], [1, 0, 0]])
        self.assertEqual(base["seconds"]["trend"][-1], [10])
        self.assertEqual(base["answers"]["hours"][15], [2, 1, 0])
        self.assertNotIn("c2c:A", json.dumps(report))

    def test_declared_metrics_use_the_same_atoms(self):
        self.describe({"id": "app-placeholder", "label": "Placeholder",
                       "fields": [{"id": "build", "values": {"ok": "成功", "failed": "失败"}}],
                       "metrics": [{"id": "builds", "label": "生成", "op": "count", "by": "build"},
                                   {"id": "fixes", "label": "修正", "op": "sum", "field": "fixes"},
                                   {"id": "tools", "label": "工具", "op": "count", "each": "tools", "by": "name",
                                    "split": "ok", "view": "table", "names": {"ace-check": "ACE"}},
                                   {"id": "bad", "op": "median"}]})
        app = stats.report(self.data, "month", self.now)["app"]
        metrics = {m["id"]: m for m in app["metrics"]}
        self.assertEqual(set(metrics), {"builds", "fixes", "tools"})  # an unknown op is left out
        self.assertEqual((metrics["builds"]["value"], metrics["builds"]["parts"]), (2, {"ok": 1, "failed": 1}))
        self.assertEqual(metrics["builds"]["values"], {"ok": "成功", "failed": "失败"})
        self.assertEqual(metrics["fixes"]["value"], 3)
        self.assertEqual(metrics["tools"]["rows"]["lookup_ace"], {"true": 1, "false": 1})
        self.assertEqual(metrics["tools"]["names"], {"ace-check": "ACE"})
        self.assertEqual(metrics["fixes"]["trend"][-1], [2, 1, 0])

    def test_messages_given_no_answer_change_no_number(self):
        self.describe({"id": "app-placeholder", "metrics": [{"id": "all", "label": "全部", "op": "count"}]})
        before = {range_: stats.report(self.data, range_, self.now) for range_ in ("day", "month")}
        AnswerLog(self.data, "qq").skip(chat="private", session="c2c:A", reason="ack", message="哦哦",
                                        after="改成 lerp 就不受影响。")
        self.assertTrue((self.data / "logs" / "qq" / "skipped.jsonl").is_file())
        self.assertEqual({range_: stats.report(self.data, range_, self.now) for range_ in ("day", "month")}, before)

    def test_unreadable_declaration_falls_back(self):
        path = self.data / "runtime" / "app.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(stats.report(self.data, "day", self.now)["app"])

    def test_no_log_is_an_empty_report(self):
        report = stats.report(self.home / "elsewhere", "day", self.now)
        self.assertEqual((report["total"], report["base"][0]["value"]), (0, 0))

    def test_endpoint_needs_the_token_and_a_known_range(self):
        (self.home / ".env").write_text("C3BOT_MODEL=placeholder\n", encoding="utf-8")
        server = create_server(ModelControl(self.home), 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(url, timeout=3) as response:
            token = response.read().decode().split('const token="', 1)[1].split('"', 1)[0]

        def get(path, key=token):
            request = urllib.request.Request(url + path, headers={"X-Panel-Token": key})
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)

        self.assertEqual(get("/api/stats?range=month")["range"], "month")
        self.assertEqual(get("/api/stats")["range"], "day")
        for path, key, code in (("/api/stats", "", 403), ("/api/stats?range=year", token, 400)):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                get(path, key)
            self.assertEqual(error.exception.code, code)


if __name__ == "__main__":
    unittest.main()
