"""Ask the bot for a catch game in the terminal, then judge what it built in the Construct 3 editor.

    .venv/Scripts/python.exe plugins/construct3/e2e/e2e_catch.py RUN [RUN ...] [--replay]

The judge does not read the bot's design. It finds in the running game the objects that fall and the one near the
bottom that catches, and checks five things with the installed preview_project.py:
  input    a tap on the left or right of the screen, an arrow key, a drag or a hold moves the catcher
  falls    something falls
  catch    with the catcher held under the lowest falling object, a number in a global or a text goes up
  lose     with the pointer held at the edge, then the catcher held away, the game ends: a text says so, or nothing
           falls any more
  restart  a tap on the left, one on the right or Space after the end brings that number back to where it started
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
sys.path.insert(0, str(HERE))
load_dotenv(HERE / ".env")  # the paths and keys the bot itself reads
from c3bot import copilot  # noqa: E402
DATA = Path(os.environ.get("C3BOT_DATA") or HERE / "var")
RAG = Path(os.environ.get("CONSTRUCT3_RAG") or HERE.parent / "Construct3-RAG")
TMP = Path(os.environ.get("TEMP", "C:/Temp"))
ASK = os.environ.get("E2E_ASK", "做个接水果的小游戏")

FIND = r"""
const vw = runtime.viewportWidth, vh = runtime.viewportHeight;
const sprites = Object.keys(runtime.objects).flatMap(n => runtime.objects[n].getAllInstances()
  .filter(i => typeof i.getBoundingBox === 'function' && i.isVisible && i.layer && i.layer.name && !('text' in i))
  .map(i => i));
const y0 = vars.y0 || {};
const falling = sprites.filter(i => y0[i.uid] !== undefined && i.y > y0[i.uid] + 5);
const fallTypes = [...new Set(falling.map(i => i.objectType.name))];
const still = sprites.filter(i => !fallTypes.includes(i.objectType.name) && i.y > vh * 0.6 && i.width < vw * 0.6
  && i.objectType.getAllInstances().length === 1);
still.sort((a, b) => b.y - a.y);
vars.fall = fallTypes; vars.catcher = still.length ? still[0].objectType.name : null;
return {fall: vars.fall, catcher: vars.catcher};
"""
SNAP = r"""
const g = {}; for (const [k, v] of Object.entries(runtime.globalVars)) if (typeof v === 'number') g[k] = v;
const texts = Object.keys(runtime.objects).flatMap(n => runtime.objects[n].getAllInstances()
  .filter(i => typeof i.text === 'string').map(i => i.text));
return {globals: g, texts};
"""
Y0 = r"""
vars.y0 = {}; for (const n of Object.keys(runtime.objects)) for (const i of runtime.objects[n].getAllInstances())
  if (typeof i.getBoundingBox === 'function') vars.y0[i.uid] = i.y;
return Object.keys(vars.y0).length;
"""
CX = "const c = vars.catcher && runtime.objects[vars.catcher].getFirstInstance(); return c ? c.x : null;"
HOLD = r"""
const end = performance.now() + {ms}; let n = 0;
while (performance.now() < end) {{
  const c = vars.catcher && runtime.objects[vars.catcher].getFirstInstance();
  const all = (vars.fall || []).flatMap(t => runtime.objects[t] ? runtime.objects[t].getAllInstances() : []);
  all.sort((a, b) => b.y - a.y);
  if (c && all.length) {{ const f = all[0]; c.x = {under} ? f.x : (f.x < runtime.viewportWidth / 2 ? runtime.viewportWidth - c.width : c.width); n++; }}
  {stop}
  await wait(0.03);
}}
return n;
"""
OVER = ("const t = Object.keys(runtime.objects).flatMap(k => runtime.objects[k].getAllInstances()"
        ".filter(i => typeof i.text === 'string').map(i => i.text)).join(' ');"
        "if (/结束|失败|游戏结束|over|Over|OVER|重新|再来|重来|重玩|输了/.test(t)) break;")


def plan(vw: int, vh: int) -> dict:
    s = [{"wait": 1.0}, {"js": Y0}, {"js": SNAP, "note": "start"}, {"wait": 1.2}, {"js": FIND, "note": "find"},
         {"js": CX, "note": "x0"}, {"tap": {"x": vw * 0.15, "y": vh * 0.85}}, {"wait": 0.4}, {"js": CX, "note": "x1"},
         {"key": "ArrowLeft", "seconds": 0.5}, {"js": CX, "note": "x2"},
         {"tap": {"x": vw * 0.85, "y": vh * 0.85}}, {"wait": 0.4}, {"js": CX, "note": "x3"},
         {"key": "ArrowRight", "seconds": 0.5}, {"js": CX, "note": "x4"},
         {"drag": {"x": vw * 0.5, "y": vh * 0.8}, "to": {"x": vw * 0.2, "y": vh * 0.8}, "seconds": 0.5},
         {"js": CX, "note": "x5"}, {"hold": {"x": vw * 0.8, "y": vh * 0.8}, "seconds": 0.6}, {"js": CX, "note": "x6"},
         {"js": SNAP, "note": "before-catch"},
         {"js": HOLD.format(ms=6000, under="true", stop=""), "timeout": 20},
         {"js": SNAP, "note": "after-catch"},
         {"hold": {"x": vw * 0.03, "y": vh * 0.6}, "seconds": 10},
         {"js": HOLD.format(ms=20000, under="false", stop=OVER), "timeout": 40},
         {"wait": 1.0}, {"js": SNAP, "note": "over"}, {"js": Y0},
         {"wait": 1.0}, {"js": FIND.replace("vars.fall = fallTypes; vars.catcher = still.length ? still[0].objectType.name : null;", ""), "note": "falls-after-over"},
         {"tap": {"x": vw * 0.25, "y": vh * 0.5}}, {"wait": 0.8}, {"tap": {"x": vw * 0.75, "y": vh * 0.5}}, {"wait": 0.8},
         {"key": "Space"}, {"wait": 0.8}, {"js": SNAP, "note": "restarted"}]
    return {"viewport": [vw, vh], "touch": True, "steps": s}


def judge(result: dict, steps_plan: list[dict]) -> dict[str, tuple[bool, str]]:
    ran = (result.get("preview") or {}).get("steps") or []
    got = {}
    for d, s in zip(ran, steps_plan):
        if s.get("note") and d.get("ok"):
            got[s["note"]] = d.get("value")
    out: dict[str, tuple[bool, str]] = {}
    find = got.get("find") or {}
    out["falls"] = (bool(find.get("fall")), f"falling {find.get('fall')}, catcher {find.get('catcher')}")
    xs = [got.get(k) for k in ("x0", "x1", "x2", "x3", "x4", "x5", "x6")]
    out["input"] = (any(x is not None and xs[0] is not None and abs(x - xs[0]) > 4 for x in xs[1:]), f"catcher x {xs}")

    def numbers(snap) -> dict[str, float]:
        if not snap:
            return {}
        nums = {f"g:{k}": v for k, v in snap["globals"].items()}
        for i, t in enumerate(snap["texts"]):
            for j, m in enumerate(re.findall(r"\d+", t)):
                nums[f"t{i}:{j}"] = float(m)
        return nums
    before, after = numbers(got.get("before-catch")), numbers(got.get("after-catch"))
    up = [k for k in after if k in before and after[k] > before[k]]
    out["catch"] = (bool(up), f"went up: {up[:4]}; texts {got.get('after-catch', {}).get('texts')}")
    over = got.get("over") or {}
    text = " ".join(over.get("texts") or [])
    still = (got.get("falls-after-over") or {}).get("fall")
    ended = bool(re.search(r"结束|失败|over|Over|OVER|重新|再来|重来|重玩|输了", text)) or still == []
    out["lose"] = (ended, f"texts {over.get('texts')}, still falling {still}")
    start, again = numbers(got.get("start")), numbers(got.get("restarted"))
    back = [k for k in up if k in again and k in start and again[k] == start[k]]
    out["restart"] = (bool(back) and ended, f"back to start: {back[:4]}; texts {got.get('restarted', {}).get('texts')}")
    return out


def run(n: str, ask: bool = True) -> None:
    session = DATA / "sessions" / f"e2ec{n}"
    out_file = DATA / "sessions" / f"e2ec{n}.out"
    if ask:
        shutil.rmtree(session, ignore_errors=True)
        proc = subprocess.run([sys.executable, "bot.py", "--cli", ASK, "--session", str(session)], cwd=HERE,
                              capture_output=True, text=True, encoding="utf-8", timeout=1200)
        out_file.write_text(proc.stdout + proc.stderr[-3000:], encoding="utf-8")
    lines = out_file.read_text(encoding="utf-8").splitlines()
    print(f"== run {n}: {sum('lookup_ace' in l for l in lines)} lookups, "
          f"{sum(l.startswith('[tool] check_design') for l in lines)} designs, "
          f"{sum(l.startswith('[tool] new_project') for l in lines)} specs")
    for l in lines:
        if l.startswith(("[tool] check_design", "[tool] new_project")):
            print("   " + (l[l.rfind(") -> ") + 5:][:240] if ") -> " in l else l[:160]))
    print("   reply: " + " / ".join(lines[lines.index("---") + 1:])[:300] if "---" in lines else "   no reply")
    if not (session / "project.c3proj").exists() or not any("[file]" in l for l in lines):
        print("   no project sent")
        return
    c3proj = json.loads((session / "project.c3proj").read_text(encoding="utf-8"))
    p = plan(int(c3proj["viewportWidth"]), int(c3proj["viewportHeight"]))
    plan_file = TMP / f"e2ec{n}-play.json"
    plan_file.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    copy = TMP / f"e2ec{n}"
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(session, copy)
    result_file = TMP / f"e2ec{n}-result.json"
    played = copilot.run_script("preview_project", [str(plan_file), "--profile", str(TMP / os.environ.get("E2E_PROFILE", "c3prof-catch")),
                                                    "--out", str(result_file)], copy, timeout=300, rag=RAG)
    result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
    verdict = judge(result, p["steps"])
    for k, (ok, why) in verdict.items():
        print(f"   {k:8} {'ok ' if ok else 'BAD'} {why[:200]}")
    tail = played.stdout.strip().splitlines()
    print(f"   {'PLAYS' if all(ok for ok, _ in verdict.values()) else 'FAILS'}; {tail[-2] if len(tail) > 1 else played.stderr[-300:]}")


if __name__ == "__main__":
    replay = "--replay" in sys.argv
    for n in (a for a in sys.argv[1:] if a != "--replay"):
        run(n, not replay)
