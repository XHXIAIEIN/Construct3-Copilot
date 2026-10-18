"""Keep the boundaries: copilot/ never imports channels, and channels/app.py is the only module under channels/ that
imports copilot. Inside channels/, core/ and model/ know no platform and no panel, a platform knows no other
platform, and the panel reads only the platform list, never a platform's code."""
import ast
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def module_of(path: Path) -> list[str]:
    parts = list(path.relative_to(REPO).with_suffix("").parts)
    return parts[:-1] if parts[-1] == "__init__" else parts


def imported(path: Path, relative: bool = False) -> set[str]:
    """Absolute module names a file imports; with relative, its relative imports too, resolved to absolute names
    (from . import x counts as both the package and package.x)."""
    names = set()
    package = module_of(path) if path.name == "__init__.py" else module_of(path)[:-1]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.add(node.module)
        elif isinstance(node, ast.ImportFrom) and relative:
            base = ".".join(package[:len(package) - node.level + 1] + ([node.module] if node.module else []))
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) == "import_module":
            names.update(arg.value for arg in node.args[:1] if isinstance(arg, ast.Constant) and isinstance(arg.value, str))
    return names


def tracked(folder: str) -> list[Path]:
    """The Python files git tracks under folder; channels/var/ holds runtime copies (backups) that are not code."""
    out = subprocess.run(["git", "ls-files", "--", f"{folder}/*.py"], cwd=REPO, capture_output=True, text=True, check=True)
    return [REPO / line for line in out.stdout.splitlines() if (REPO / line).is_file()]


def importers(folder: str, package: str, relative: bool = False) -> list[str]:
    return sorted(str(path.relative_to(REPO).as_posix()) for path in tracked(folder)
                  if any(name == package or name.startswith(package + ".") for name in imported(path, relative)))


class BoundaryTests(unittest.TestCase):
    def test_copilot_does_not_import_channels(self):
        self.assertEqual(importers("copilot", "channels"), [])

    def test_only_app_imports_copilot(self):
        self.assertEqual(importers("channels", "copilot"), ["channels/app.py"])

    def test_no_channel_module_loads_dotenv_on_import(self):
        users = sorted(str(p.relative_to(REPO).as_posix()) for p in tracked("channels")
                       if "load_dotenv(" in p.read_text(encoding="utf-8"))
        self.assertEqual(users, [])

    def test_core_and_model_know_no_platform_and_no_panel(self):
        for folder in ("channels/core", "channels/model"):
            for package in ("channels.platforms", "channels.panel"):
                with self.subTest(folder=folder, package=package):
                    self.assertEqual(importers(folder, package, relative=True), [])

    def test_a_platform_imports_no_other_platform(self):
        platforms = sorted(p.name for p in (REPO / "channels" / "platforms").iterdir() if (p / "__main__.py").is_file())
        self.assertIn("qq", platforms)
        for name in platforms:
            for other in platforms:
                if other != name:
                    with self.subTest(platform=name, other=other):
                        self.assertEqual(importers(f"channels/platforms/{name}", f"channels.platforms.{other}", True), [])

    def test_panel_reads_the_platform_list_but_no_platform_code(self):
        users = sorted({name for path in tracked("channels/panel") for name in imported(path, relative=True)
                        if name.startswith("channels.platforms.")})
        self.assertEqual([name for name in users if name not in {"channels.platforms.PANEL", "channels.platforms.PLATFORMS",
                                                                  "channels.platforms.Platform"}], [])
