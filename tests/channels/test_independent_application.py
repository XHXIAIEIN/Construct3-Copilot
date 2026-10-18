"""Verify that the QQ transport runs any application with handle(request), without Construct or a model client."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

REPO = Path(__file__).resolve().parents[2]


class Echo:
    def __init__(self):
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        return {"text": request["text"], "files": ["file-placeholder"], "trace": [request["session_id"]]}


class IndependentApplicationTests(unittest.TestCase):
    def test_cli_passes_the_request_and_prints_the_delivery(self):
        from channels.qq.bot import ask_cli
        application = Echo()
        out = io.StringIO()
        with redirect_stdout(out):
            ask_cli(application, "example", data_dir=Path("data-placeholder"))
        request = application.requests[0]
        self.assertEqual((request["text"], request["session_id"], request["history"], request["attachments"]),
                         ("example", "cli", [], []))
        self.assertEqual(request["session_dir"], Path("data-placeholder") / "sessions" / "cli")
        self.assertEqual(out.getvalue().splitlines(), ["[tool] cli", "example", "[file] file-placeholder"])

    def test_transport_model_and_panel_load_without_copilot_or_a_model_client(self):
        code = '''
import json, sys
import channels.qq.bot, channels.qq.files, channels.core.receipt, channels.panel.server, channels.model.settings
print(json.dumps(sorted(m for m in sys.modules if m == "copilot" or m.startswith("copilot.") or m == "openai")))
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
