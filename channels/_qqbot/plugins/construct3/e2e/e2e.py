"""Ask the bot for a gomoku game in the terminal, then play what it built in the Construct 3 editor.

    .venv/Scripts/python.exe specs/e2e.py RUN [RUN ...]

Each run: bot.py --cli "做个五子棋" into sessions/e2e<RUN>, then the preview player of the RAG plays the plan of
make_play.py (a blocked line, a taken cell, a win across, the restart, a win on a diagonal) on a copy under %TEMP%.
Prints the bot's tool calls in short, its reply, and each check with the value the game held.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402

HERE = Path(__file__).resolve().parents[3]  # the bot folder
load_dotenv(HERE / ".env")  # the paths and keys the bot itself reads
DATA = Path(os.environ.get("C3BOT_DATA") or HERE / "var")
RAG = Path(os.environ.get("CONSTRUCT3_RAG") or HERE.parent / "Construct3-RAG")
SCRIPTS = RAG / "skills" / "construct3-agent-plugin" / "scripts"
TMP = Path(os.environ.get("TEMP", "C:/Temp"))
# step -> state, turn, pieces, a word the status shows (None: any)
EXPECT = {18: (0, 1, 8, None), 21: (0, 1, 8, None), 28: (2, 1, 9, "黑"), 34: (0, 1, 0, None), 55: (None, 2, 10, "白")}


def names(project: Path) -> tuple[str, str, str, str, str]:
    """The created piece, the state global and the Cell's index variables, read from what the bot built."""
    sheet = json.loads(next((project / "eventSheets").glob("*.json")).read_text(encoding="utf-8"))
    text = json.dumps(sheet)
    piece = re.search(r'"object-to-create": "([^"]+)"', text).group(1)
    globals_ = [e["name"] for e in sheet["events"] if e.get("eventType") == "variable"]
    state = next((g for g in globals_ if g != "turn"), "state")
    layout = json.loads((project / "layouts" / "Game.json").read_text(encoding="utf-8"))
    cell = next(i for ly in layout["layers"] for i in ly["instances"] if i["type"] == "Cell")
    cols = list(cell["instanceVariables"])
    labels = re.findall(r'"id": "set-text", "objectClass": "([^"]+)"', text)
    return piece, state, cols[0], cols[1], max(set(labels), key=labels.count)


def run(n: str, ask: bool = True) -> None:
    session = DATA / "sessions" / f"e2e{n}"
    if ask:
        shutil.rmtree(session, ignore_errors=True)
    proc = subprocess.CompletedProcess([], 0, (DATA / "sessions" / f"e2e{n}.out").read_text(encoding="utf-8"), "") if not ask else subprocess.run([sys.executable, "bot.py", "--cli", "做个五子棋", "--session", str(session)], cwd=HERE,
                          capture_output=True, text=True, encoding="utf-8", timeout=1200)
    (DATA / "sessions" / f"e2e{n}.out").write_text(proc.stdout, encoding="utf-8")
    lines = proc.stdout.splitlines()
    calls = [l for l in lines if l.startswith("[tool] new_project")]
    print(f"== run {n}: {sum('lookup_ace' in l for l in lines)} lookups, {len(calls)} specs")
    for l in calls:
        print("   " + l[l.rfind(") -> ") + 5:][:200] if ") -> " in l else "   " + l[:200])
    print("   reply: " + " / ".join(lines[lines.index("---") + 1:])[:300] if "---" in lines else proc.stdout[-500:])
    if not (session / "project.c3proj").exists() or not any("[file]" in l for l in lines):
        print("   no project sent")
        return
    try:
        piece, state, cv, rv, label = names(session)
    except (StopIteration, AttributeError, KeyError, IndexError) as e:
        print(f"   cannot read the board: {e!r}")
        return
    plan = TMP / f"e2e{n}-play.json"
    c3proj = json.loads((session / "project.c3proj").read_text(encoding="utf-8"))
    layout = json.loads((session / "layouts" / "Game.json").read_text(encoding="utf-8"))
    side = round(sum(i["type"] == "Cell" for ly in layout["layers"] for i in ly["instances"]) ** 0.5)
    subprocess.run([sys.executable, str(Path(__file__).with_name("make_play.py")), piece, state, str(plan), cv, rv, label,
                    *(str(c3proj[k]) for k in ("viewportWidth", "viewportHeight")), str(side)], check=True)
    copy = TMP / f"e2e{n}"
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(session, copy)
    played = subprocess.run([sys.executable, str(SCRIPTS / "preview_project.py"), str(plan), "--project", str(copy),
                             "--profile", str(TMP / os.environ.get("E2E_PROFILE", "c3prof"))], capture_output=True, text=True, encoding="utf-8",
                            timeout=200)
    held = {}
    for l in played.stdout.splitlines():
        m = re.match(r"\s+(\d+) js .*: (\[.*\])$", l)
        if m:
            held[int(m.group(1))] = json.loads(m.group(2))
    ok = True
    for step, want in EXPECT.items():
        got = held.get(step)
        good = got is not None and all(w is None or w == g for w, g in zip(want[:3], got)) and (
            want[3] is None or want[3] in str(got[3]))
        ok &= good
        print(f"   step {step}: {'ok ' if good else 'BAD'} {got}")
    print(f"   {'PLAYS' if ok else 'FAILS'}; {played.stdout.strip().splitlines()[-2] if played.stdout.strip() else played.stderr[-300:]}")
    judge2(n, copy, piece, cv, rv, label, *(str(c3proj[k]) for k in ("viewportWidth", "viewportHeight")), side)

WIN = ("胜", "赢")


def judge2(n: str, copy: Path, piece: str, cv: str, rv: str, label: str, vw: str, vh: str, side: int,
           cells: str = "Cell") -> None:
    """The second judge: make_play2.py's plan, which fits any board and any state names."""
    plan = TMP / f"e2e{n}-play2.json"
    subprocess.run([sys.executable, str(Path(__file__).with_name("make_play2.py")), piece, str(plan), cv, rv, label, vw, vh,
                    str(side), cells], check=True)
    out = TMP / f"e2e{n}-play2-result.json"
    subprocess.run([sys.executable, str(SCRIPTS / "preview_project.py"), str(plan), "--project", str(copy),
                    "--profile", str(TMP / os.environ.get("E2E_PROFILE", "c3prof")), "--out", str(out)],
                   capture_output=True, text=True, encoding="utf-8", timeout=200)
    ran = json.loads(out.read_text(encoding="utf-8")).get("preview", {}).get("steps", []) if out.exists() else []
    steps = json.loads(plan.read_text(encoding="utf-8"))["steps"]
    got = {s["note"]: d.get("value") for d, s in zip(ran, steps) if s.get("note") and not s["note"].startswith("cell") and d.get("ok")}
    want = {"blocked": (8, None, False), "taken": (8, None, False), "black-wins": (9, "黑", True),
            "restarted": (0, None, False), "white-wins": (10, "白", True)}
    ok = True
    for note, (count, side_word, won) in want.items():
        v = got.get(note)
        good = bool(v) and v[0] == count and (any(w in v[1] for w in WIN) == won) and (side_word is None or side_word in v[1])
        ok &= good
        print(f"   v2 {note:10} {'ok ' if good else 'BAD'} {v[:2] if v else None}")
    print(f"   v2 {'PLAYS' if ok else 'FAILS'}")



if __name__ == "__main__":
    # --replay N plays the project of an earlier run again without asking the bot
    replay = "--replay" in sys.argv
    for n in (a for a in sys.argv[1:] if a != "--replay"):
        run(n, not replay)
