"""Verify that a transport application can run without Construct or a model client."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ApplicationLoaderTests(unittest.TestCase):
    def test_independent_application_preserves_request_and_delivery(self):
        root = Path(__file__).resolve().parents[1]
        scratch = root / ".tmp" / "loader-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            home = Path(temp)
            plugin = home / "plugins" / "echo"
            plugin.mkdir(parents=True)
            (plugin / "__init__.py").write_text('''
class Application:
    def handle(self, request):
        return {"text": request["text"], "files": [request["attachments"][0]["url"]],
                "trace": [request["session_id"], request["history"][0]["content"]]}
def create_application(**settings):
    return Application()
''', encoding="utf-8")
            code = '''
import json, sys
from pathlib import Path
from qqbot.knowledge import load_application
app = load_application("echo", home=Path(sys.argv[1]), data_dir=Path(sys.argv[1])/"var", settings={})
print(json.dumps(app.handle({"text":"example", "session_id":"session-placeholder",
    "history":[{"content":"earlier"}], "attachments":[{"url":"file-placeholder"}]})))
assert not any(m == "copilot" or m.startswith("copilot.") or m == "openai" for m in sys.modules)
'''
            result = subprocess.run([sys.executable, "-c", code, str(home)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                "text": "example", "files": ["file-placeholder"],
                "trace": ["session-placeholder", "earlier"],
            })

    def test_application_name_cannot_escape_plugin_folder(self):
        from qqbot.knowledge import load_application
        with self.assertRaises(ValueError):
            load_application("../example", home=Path.cwd(), data_dir=Path.cwd(), settings={})
