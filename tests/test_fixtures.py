import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / ".claude" / "skills" / "construct3-copilot" / "scripts" / "validate_output.py"
FIXTURES = ROOT / "tests" / "fixtures"


class FixtureValidationTests(unittest.TestCase):
    def test_fixtures_validate(self):
        for path in sorted(FIXTURES.glob("*.json")):
            proc = subprocess.run(
                ["python3", str(VALIDATOR), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            msg = f"{path.name} failed:\n{proc.stdout}\n{proc.stderr}"
            self.assertEqual(proc.returncode, 0, msg)


if __name__ == "__main__":
    unittest.main()
