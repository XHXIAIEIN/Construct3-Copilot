"""Check package entrypoints after moving launch code into the package."""
import subprocess
import sys
import unittest


class EntrypointTests(unittest.TestCase):
    def test_qq_and_grader_help(self):
        for module in ("qqbot.qq", "qqbot.grader"):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, "-m", module, "--help"],
                                        stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                self.assertIn(b"usage:", result.stdout)
