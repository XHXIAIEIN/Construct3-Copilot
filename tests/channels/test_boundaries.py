"""Keep the boundary between the Construct application and the channels: copilot/ never imports channels, and
channels/app.py is the only module under channels/ that imports copilot."""
import ast
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def imported(path: Path) -> set[str]:
    """Absolute module names a file imports; relative imports stay inside their own package."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) == "import_module":
            names.update(arg.value for arg in node.args[:1] if isinstance(arg, ast.Constant) and isinstance(arg.value, str))
    return names


def tracked(folder: str) -> list[Path]:
    """The Python files git tracks under folder; channels/var/ holds runtime copies (backups) that are not code."""
    out = subprocess.run(["git", "ls-files", "--", f"{folder}/*.py"], cwd=REPO, capture_output=True, text=True, check=True)
    return [REPO / line for line in out.stdout.splitlines() if (REPO / line).is_file()]


def importers(folder: str, package: str) -> list[str]:
    return sorted(str(path.relative_to(REPO).as_posix()) for path in tracked(folder)
                  if any(name == package or name.startswith(package + ".") for name in imported(path)))


class BoundaryTests(unittest.TestCase):
    def test_copilot_does_not_import_channels(self):
        self.assertEqual(importers("copilot", "channels"), [])

    def test_only_app_imports_copilot(self):
        self.assertEqual(importers("channels", "copilot"), ["channels/app.py"])

    def test_no_channel_module_loads_dotenv_on_import(self):
        users = sorted(str(p.relative_to(REPO).as_posix()) for p in tracked("channels")
                       if "load_dotenv(" in p.read_text(encoding="utf-8"))
        self.assertEqual(users, [])
