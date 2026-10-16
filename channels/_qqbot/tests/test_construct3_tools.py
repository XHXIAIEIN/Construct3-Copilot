"""Offline checks against the configured Construct3-Agent-Skills plugin and examples clone."""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from c3bot import construct3, edits
from plugins.construct3 import newproject, tools

ROOT = Path(__file__).resolve().parents[1]


class ConstructToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        offline = patch.dict(os.environ, {"CONSTRUCT3_RAG_OFFLINE": "1"})
        offline.start()
        cls.addClassCleanup(offline.stop)
        cls.scratch = ROOT / ".tmp" / "reference-migration" / "tests"
        cls.scratch.mkdir(parents=True, exist_ok=True)
        cls.environment = {**os.environ, "CONSTRUCT3_RAG_OFFLINE": "1"}
        if not (construct3.SCRIPTS / "lookup_ace.py").is_file():
            raise AssertionError("Set CONSTRUCT3_AGENT_SKILLS to a Construct3-Agent-Skills clone or plugin folder")

    def paths_in_process(self, **overrides):
        env = {**self.environment, **overrides}
        code = ("import json; from c3bot.construct3 import PLUGIN_ROOT,RAG,examples_root; "
                "print(json.dumps([str(PLUGIN_ROOT),str(RAG),str(examples_root())]))")
        run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True,
                             text=True, encoding="utf-8", timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return list(map(Path, json.loads(run.stdout)))

    def test_clone_and_plugin_overrides(self):
        plugin = construct3.PLUGIN_ROOT.resolve()
        clone = construct3.shared().clone_root(plugin)
        for selected in (clone, plugin):
            with self.subTest(selected=selected):
                found, data, examples = self.paths_in_process(CONSTRUCT3_AGENT_SKILLS=str(selected), CONSTRUCT3_RAG="", C3_EXAMPLES="")
                self.assertEqual(found.resolve(), plugin)
                self.assertEqual(data.resolve(), plugin)
                self.assertEqual(examples.resolve(), newproject.EXAMPLES.resolve())

    def test_data_and_examples_overrides(self):
        data = self.scratch / "source-data"
        examples = self.scratch / "official-examples"
        found, actual_data, actual_examples = self.paths_in_process(
            CONSTRUCT3_AGENT_SKILLS=str(construct3.PLUGIN_ROOT), CONSTRUCT3_RAG=str(data), C3_EXAMPLES=str(examples))
        self.assertEqual(found.resolve(), construct3.PLUGIN_ROOT.resolve())
        self.assertEqual(actual_data, data)
        self.assertEqual(actual_examples, examples)

    def test_real_lookups(self):
        calls = [("lookup_ace", ["System", "wait"], '"id": "wait"'),
                 ("lookup_script_api", ["IRuntime"], "class IRuntime"),
                 ("search_guides", ["wait", "--examples", "0"], "wait-and-time-scale.md")]
        for script, args, expected in calls:
            with self.subTest(script=script):
                code, output = tools.run_script_code(script, args, locale="en-US")
                self.assertEqual(code, 0, output)
                self.assertIn(expected, output)

    def test_lookup_failure_exit_code(self):
        code, output = tools.run_script_code("lookup_script_api", ["NoSuchInterfaceForPathTest"])
        self.assertEqual(code, 1, output)
        self.assertTrue(output)

    def test_design_reference(self):
        self.assertTrue(newproject.design_guide().startswith("## The design"))

    def test_official_example_read(self):
        output = newproject.read_example("system-wait", construct3.RAG, "en-US")
        self.assertIn("== Event sheet 1", output)
        self.assertIn("On start of layout", output)
        self.assertNotIn("can't open file", output)

    def test_e2e_script_discovery(self):
        with patch("dotenv.load_dotenv"):
            for name in ("e2e.py", "e2e_catch.py"):
                with self.subTest(script=name):
                    module = runpy.run_path(str(ROOT / "plugins/construct3/e2e" / name))
                    self.assertEqual(module["SCRIPTS"].resolve(), construct3.SCRIPTS.resolve())
                    self.assertTrue((module["SCRIPTS"] / "preview_project.py").is_file())

    def test_grader_tool_context(self):
        with patch("dotenv.load_dotenv"):
            module = runpy.run_path(str(ROOT / "grader.py"))
        result = subprocess.CompletedProcess([], 0, stdout="Offline grade", stderr="")
        item = dict(key="sample", when="sample", question="sample", earlier="", tools="", reply="sample", snap="none")
        with patch("subprocess.run", return_value=result) as run:
            self.assertEqual(module["grade"](item), "Offline grade")
        self.assertEqual(run.call_args.kwargs["cwd"].resolve(), construct3.PLUGIN_ROOT.resolve())
        self.assertIn("skills/construct3-agent-plugin/SKILL.md", run.call_args.kwargs["input"])
        self.assertIn(construct3.RAG.as_posix(), run.call_args.kwargs["input"])

    def test_build_check_and_package(self):
        spec = {"name": "ToolPathSmoke", "objects": [{"name": "Token", "plugin": "Sprite", "size": [2, 2]}],
                "layouts": [{"name": "Game", "sheet": "Game", "layers": [{"name": "Main"}],
                             "instances": [{"object": "Token", "layer": "Main", "col": 5, "row": 6}]}],
                "sheets": [{"name": "Game", "events": [{"eventType": "comment", "text": "Offline tool path check"}]}]}
        with tempfile.TemporaryDirectory(dir=self.scratch) as folder:
            folder = Path(folder)
            source, project = folder / "spec.json", folder / "project"
            source.write_text(json.dumps(spec), encoding="utf-8")
            built = subprocess.run([sys.executable, str(ROOT / "plugins/construct3/spec_build.py"), str(source),
                                    "--out", str(project), "--rag", str(construct3.RAG), "--locale", "en-US"],
                                   cwd=ROOT, env=self.environment, capture_output=True, text=True, encoding="utf-8", timeout=90)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertTrue((project / "project.c3proj").is_file())
            code, output = tools.run_script_code("check_project", [], project=project, locale="en-US")
            self.assertEqual(code, 0, output)
            self.assertIn("ok:", output)
            # Keep packaging sidecars in this test's scratch folder.
            edit_root, new_root = edits.ROOT, newproject.MARKS
            try:
                edits.ROOT, newproject.MARKS = folder / "edits", folder / "new"
                for target in (edits.pack(project), newproject.pack(project)):
                    with zipfile.ZipFile(target) as archive:
                        self.assertIn("project.c3proj", archive.namelist())
                        self.assertTrue(any(name.startswith("eventSheets/") for name in archive.namelist()))
            finally:
                edits.ROOT, newproject.MARKS = edit_root, new_root


if __name__ == "__main__":
    unittest.main()
