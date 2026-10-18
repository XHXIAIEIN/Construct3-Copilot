"""Verify panel requests, serialized actions and visible failure outcomes."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock

from qqbot.model_manager.server import create_server


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.control = Mock(home=Path.cwd())
        self.control.status.return_value = {"current": {"model": "example"}, "models": [], "ollama": {"online": False}}
        self.server = create_server(self.control, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        with urllib.request.urlopen(self.url) as response:
            self.page = response.read().decode()
        self.token = self.page.split('const token="', 1)[1].split('"', 1)[0]

    def request(self, value, token=None):
        req = urllib.request.Request(self.url + "/api/action", data=json.dumps(value).encode(),
                                     headers={"X-Panel-Token": self.token if token is None else token,
                                              "Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=3)

    def test_page_and_status_are_served(self):
        self.assertIn('<dialog id="api-dialog"', self.page)
        self.assertIn('id="api-key-env"', self.page)
        self.assertNotIn("__PANEL_TOKEN__", self.page)
        with urllib.request.urlopen(self.url + "/api/status") as response:
            self.assertEqual(json.load(response)["status"]["current"]["model"], "example")

    def test_post_rejects_cross_page_token(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({"action": "start"}, token="wrong")
        self.assertEqual(error.exception.code, 403)
        self.control.start.assert_not_called()

    def test_busy_operation_is_not_executed_twice(self):
        entered, release = threading.Event(), threading.Event()
        def warm(model):
            entered.set()
            release.wait(3)
            return {"ok": True, "message": "loaded"}
        self.control.warm.side_effect = warm
        self.addCleanup(release.set)
        with self.request({"action": "warm", "model": "example"}) as response:
            self.assertEqual(response.status, 202)
        self.assertTrue(entered.wait(2))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({"action": "switch", "model": "example"})
        self.assertEqual(error.exception.code, 409)
        self.control.switch.assert_not_called()
        release.set()

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({"action": "shell"})
        self.assertEqual(error.exception.code, 400)

    def test_browser_disconnect_during_headers_or_body_ends_response(self):
        handler_type = self.server.RequestHandlerClass
        for phase in ("headers", "body"):
            for error in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                with self.subTest(phase=phase, error=error):
                    handler = handler_type.__new__(handler_type)
                    handler.send_response = Mock()
                    handler.send_header = Mock()
                    handler.end_headers = Mock(side_effect=error() if phase == "headers" else None)
                    handler.wfile = Mock()
                    if phase == "body":
                        handler.wfile.write.side_effect = error()
                    handler.send(200, {"status": "ready"})
                    self.assertTrue(handler.close_connection)
                    handler.send_response.assert_called_once_with(200)


if __name__ == "__main__":
    unittest.main()
