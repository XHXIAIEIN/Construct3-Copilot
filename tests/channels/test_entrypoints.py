"""Check the channel entrypoints start without .env, Copilot or a model."""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class EntrypointTests(unittest.TestCase):
    def test_qq_grader_and_panel_help(self):
        for module in ("channels.qq", "channels.grader", "channels.panel"):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, "-m", module, "--help"], cwd=REPO,
                                        stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                self.assertIn(b"usage:", result.stdout)
