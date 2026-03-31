import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class QualityToolTests(unittest.TestCase):
    def test_validate_skill_docs_passes(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_skill_docs.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)

    def test_find_similar_failures_returns_match(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "find_similar_failures.py"),
                "unknown action id toggle-boolean",
                "--top",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
        self.assertIn("invalid-system-boolean-ace", proc.stdout)

    def test_log_failure_case_dry_run_outputs_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "log_failure_case.py"),
                "--case-id",
                "unit-test-dry-run",
                "--query",
                "unit test",
                "--signature",
                "none",
                "--root-cause",
                "none",
                "--fix",
                "none",
                "--tags",
                "tests,ci",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
        parsed = json.loads(proc.stdout.strip())
        self.assertEqual(parsed["case_id"], "unit-test-dry-run")


if __name__ == "__main__":
    unittest.main()
