"""Build a texture with spec_build: the backdrop's checker on a TiledBg, tinted by its instance."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SIBLINGS = REPO.parent if (REPO.parent / "Construct3-Agent-Skills").is_dir() else REPO.parents[2].parent
SKILLS = Path(os.environ.get("COPILOT_SKILLS_ROOT") or SIBLINGS / "Construct3-Agent-Skills")
RAG = Path(os.environ.get("COPILOT_RAG") or SIBLINGS / "Construct3-RAG")
pytestmark = pytest.mark.skipif(not (SKILLS.is_dir() and RAG.is_dir()), reason="needs Construct3-Agent-Skills and -RAG")

CLOTH = {"name": "Tablecloth", "theme": "day",
         "objects": [{"name": "Cloth", "plugin": "TiledBg", "pattern": "checker", "size": [16, 14]}],
         "layouts": [{"name": "Game", "sheet": "Game",
                      "layers": [{"name": "Background", "color": "canvas"}, {"name": "Game"}],
                      "instances": [{"object": "Cloth", "layer": "Game", "col": "center", "row": "center",
                                     "color": "solid"}]}],
         "sheets": [{"name": "Game", "events": [
             {"eventType": "comment", "text": "Bend the cloth: the top recedes, the front hangs straight down"},
             {"eventType": "block", "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}],
              "actions": [{"id": "set-mesh-size", "objectClass": "Cloth",
                           "parameters": {"cols": "2", "rows": "3", "copy-from-old-mesh": False}}]}]}]}


def build(spec: dict, tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    path, out = tmp_path / "spec.json", tmp_path / "project"
    path.write_text(json.dumps(spec), encoding="utf-8")
    env = {**os.environ, "COPILOT_SKILLS_ROOT": str(SKILLS), "COPILOT_DATA": str(tmp_path / "data")}
    proc = subprocess.run([sys.executable, str(REPO / "copilot/providers/construct3/spec_build.py"), str(path),
                           "--out", str(out), "--rag", str(RAG), "--locale", "zh-CN"],
                          capture_output=True, text=True, encoding="utf-8", timeout=110, env=env)
    return proc, out


def test_checker_texture_is_a_tinted_tiledbg(tmp_path):
    proc, out = build(CLOTH, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cloth = json.loads((out / "objectTypes/Cloth.json").read_text(encoding="utf-8"))
    assert cloth["plugin-id"] == "TiledBg"
    assert (out / "images/cloth.png").is_file()
    layout = json.loads((out / "layouts/Game.json").read_text(encoding="utf-8"))
    placed = next(i for layer in layout["layers"] for i in layer["instances"] if i["type"] == "Cloth")
    assert (placed["world"]["width"], placed["world"]["height"]) == (16 * 32, 14 * 32)
    assert placed["world"]["color"] != [1, 1, 1, 1]


def test_color_on_a_sprite_is_refused(tmp_path):
    spec = json.loads(json.dumps(CLOTH))
    spec["objects"][0] = {"name": "Cloth", "plugin": "Sprite", "size": [16, 14]}
    spec["sheets"][0]["events"] = spec["sheets"][0]["events"][:1]
    proc, _ = build(spec, tmp_path)
    assert proc.returncode == 1
    assert "tints a TiledBg" in proc.stdout + proc.stderr
