import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / ".agents" / "skills" / "construct3-copilot" / "scripts" / "validate_output.py"
FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLES = ROOT / "tests" / "examples"


class FixtureValidationTests(unittest.TestCase):
    def test_fixtures_validate(self):
        paths = list(sorted(FIXTURES.glob("*.json"))) + list(sorted(EXAMPLES.glob("*.json")))
        for path in paths:
            proc = subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            msg = f"{path.name} failed:\n{proc.stdout}\n{proc.stderr}"
            self.assertEqual(proc.returncode, 0, msg)


if __name__ == "__main__":
    unittest.main()
