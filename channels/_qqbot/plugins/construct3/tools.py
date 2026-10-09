"""The model's tools: the schemas it sees and the functions behind them, which run the scripts of the
construct3-agent-plugin skill over the RAG clone or the person's project."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from c3bot import edits
from . import newproject
from c3bot.config import HOME, LOCALE, RAG

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_ace",
            "description": (
                "Find Construct 3 conditions, actions and expressions of System, of a plugin or behavior "
                "(id or display name, e.g. Sprite, Timer, 计时器), or the parameters of an effect. "
                "Every word must occur in the ACE's id, name or script name. Prints each match with its parameters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {"type": "string", "description": "System, a plugin, behavior or effect"},
                    "words": {"type": "array", "items": {"type": "string"}, "description": "filter words, may be empty"},
                },
                "required": ["object"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_examples",
            "description": (
                "Search the official Construct 3 example projects by words in their name, description, tags "
                "or the addons they use (e.g. Platform, Tween, 平台). Returns up to 8 matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {"words": {"type": "array", "items": {"type": "string"}}},
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_guides",
            "description": (
                "Search tested Construct 3 runtime facts and pitfalls (picking, triggers, input and touch, timers, chasing and moving toward a target, "
                "tween, wait, layers, creating objects, functions, storage). Words in English, e.g. "
                "['layer', 'interactive', 'touch']. Call it for every how-to or why-does-this-not-work question."
            ),
            "parameters": {
                "type": "object",
                "properties": {"words": {"type": "array", "items": {"type": "string"}}},
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_script_api",
            "description": (
                "Find a method, property or interface of the Construct 3 JavaScript/TypeScript scripting API "
                "(e.g. isMouseButtonDown, getAllInstances, IMouseObjectType) in the official .d.ts files. Use it, "
                "not lookup_ace, for anything written in a script."
            ),
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        },
    },
]

PROJECT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "print_layout",
            "description": (
                "Print the user's layouts: layers bottom to top, each object's position, size, opacity and text, "
                "and which object a text lies on. Use it for where something is, how big, what covers what, and "
                "whether a label sits on its button ('on no object' means it does not). layouts: names, default "
                "all; layer: one layer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "layouts": {"type": "array", "items": {"type": "string"}},
                    "layer": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "print_sheet",
            "description": (
                "Print the user's event sheets as the editor words them, numbered. No sheets: every sheet. "
                "outline=true prints only the numbering of a long sheet; events='40-60' prints a range of one sheet; "
                "show=5 prints event 5 of one sheet as JSON, to change and put back with edit_sheet's replace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheets": {"type": "array", "items": {"type": "string"}},
                    "events": {"type": "string"},
                    "outline": {"type": "boolean"},
                    "show": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_sheet",
            "description": (
                "Change one event sheet of the user's project with a plan: a list of operations addressed by the "
                "event numbers print_sheet shows now. "
                '[{"after": 8, "events": [{"eventType": "block", "conditions": [...], "actions": [...]}]}, '
                '{"event": 9, "add-actions": [<the write: JSON of lookup_ace, without "sid">]}, '
                '{"event": 7, "action": 2, "set": {"parameters": {"text": "\\"Score: \\" & score"}}}, '
                '{"event": 6, "action": 3, "remove": true}, {"remove": 4}, {"move": 7, "after": 6}, '
                '{"replace": 5, "events": [...]}, {"before": 1, "events": [{"eventType": "variable", "name": "best", '
                '"initialValue": "0"}]}]. A new top-level event needs {"eventType": "comment", "text": "..."} above it '
                "in the same events list. The plan is checked first; a refused plan writes nothing and says what to fix. "
                "A project with no event sheet (one run by scripts) gets one with new=true: name it, and the plan "
                'fills it from {"into": 0, "events": [...]}.'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {"type": "string", "description": "the event sheet's name"},
                    "plan": {"type": "array", "items": {"type": "object"}},
                    "new": {"type": "boolean", "description": "create the sheet first; the layouts run it when the project has no other sheet"},
                },
                "required": ["sheet", "plan"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo_edit",
            "description": "Undo the last edit_sheet change, or with all=true every change, back to the project as sent.",
            "parameters": {"type": "object", "properties": {"all": {"type": "boolean"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_project",
            "description": "Send the user's project as it is now back to them as a .c3p file, after the reply.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_script",
            "description": (
                "Read a JavaScript or TypeScript file of the user's project, e.g. scripts/main.js, numbered. "
                "print_sheet and check_project name the scripts; at most 200 lines a call."
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "first": {"type": "integer"}, "last": {"type": "integer"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_project",
            "description": (
                "Check the user's project against the schemas and the editor's load rules, and the runtime traps "
                "the checker knows. Each finding names the sheet and event number. style=true adds style warnings."
            ),
            "parameters": {"type": "object", "properties": {"style": {"type": "boolean"}}},
        },
    },
]

GROUP_PROMPT = """This message comes from a QQ group. A file sent to the group reaches you only when someone replies to it and
@-mentions you in that reply; to look at a project, ask them to do that, or to send the .c3p in a private chat."""

PROJECT_PROMPT = """The user sent a Construct 3 project. print_sheet reads its event sheets, check_project runs the checker, and
lookup_ace also takes the project's object names (e.g. Player) and lists their behaviors' ACEs. Read the sheet
before you talk about it, cite events by sheet and number ("Game 第 12 条事件"), and run check_project when
the user asks what is wrong. A project written in JavaScript has its logic in scripts: read them with
read_script and answer from the code. Answer what was asked; do not report on parts nobody asked about.

Change the project only when the person asks for a change, not for a question. To change it: print the sheet,
look up every condition, action and expression you will write with lookup_ace (its write: line is the JSON to
copy, without "sid"), then call edit_sheet with one plan. A refused plan wrote nothing: fix what the refusal
names and call edit_sheet again. After a written change the edited project goes to the person as a file after
your reply: say in plain words what now happens differently in the game, then that the edited file follows.
If your own change leaves a problem you can name, fix it with another edit_sheet call before you reply; do not
hand it to the person as a step.
"撤销" or wanting the old version back means undo_edit (all=true for every change). send_project sends the
project as it is. A project with no event sheet gets one with edit_sheet new=true (name it "Game"). Its scripts
still run beside the new events, so when events replace what a script did, tell the person to delete that
script in the editor's Project panel, as one step."""

# the tools whose output comes from the person's own project, so the names in it are real there
PROJECT_READERS = ("print_sheet", "print_layout", "read_script", "check_project")


def run_script_code(name: str, args: list[str], project: Path | None = None, limit: int = 6000,
                    locale: str = LOCALE) -> tuple[int, str]:
    """Run a script of the construct3-agent-plugin skill; return its exit code and what it printed."""
    script = RAG / "skills" / "construct3-agent-plugin" / "scripts" / f"{name}.py"
    cmd = [sys.executable, str(script), "--rag", str(RAG), "--locale", locale, "--limit", str(limit)]
    if project:
        cmd += ["--project", str(project)]
    proc = subprocess.run(cmd + args, capture_output=True, text=True, encoding="utf-8", timeout=90, cwd=HOME)
    return proc.returncode, (proc.stdout + proc.stderr).strip() or "no output"


def run_script(name: str, args: list[str], project: Path | None = None, limit: int = 6000, locale: str = LOCALE) -> str:
    """Run a script of the construct3-agent-plugin skill and return what it printed."""
    return run_script_code(name, args, project, limit, locale)[1]


def lookup_ace(object: str, words: list[str] | None = None, project: Path | None = None) -> str:
    return run_script("lookup_ace", [object, *(words or [])], project)


def lookup_script_api(name: str) -> str:
    """An interface with its members, or a member with its declaration: the RAG's lookup_script_api.py."""
    return run_script("lookup_script_api", [name])


def search_examples(words: list[str]) -> str:
    """The official examples that hold the words, "id: name. description", from the RAG's search_guides.py.
    The commands it prints under each one are left out: the bot reads an example with read_example."""
    out = run_script("search_guides", [*words, "--pitfalls", "0"])
    return "\n".join(line for line in out.splitlines() if line != "examples:" and not line.startswith("  "))


def search_guides(words: list[str]) -> str:
    """The pitfall entries that hold the words, each in full with its file and line: the RAG's search_guides.py."""
    return run_script("search_guides", [*words, "--examples", "0"])


HANDLERS = {
    "lookup_ace": lookup_ace,
    "search_examples": search_examples,
    "search_guides": search_guides,
    "lookup_script_api": lookup_script_api,
}


def print_sheet(project: Path, sheets: list[str] | None = None, events: str | None = None, outline: bool = False,
                show: int | None = None) -> str:
    args = [*(["--events", events] if events else []), *(["--outline"] if outline else []),
            *(["--show", str(show)] if show else []), *(sheets or [])]
    return run_script("print_sheet", ["--review", *args], project, limit=8000)


def print_layout(project: Path, layouts: list[str] | None = None, layer: str | None = None) -> str:
    return run_script("print_layout", [*(layouts or []), *(["--layer", layer] if layer else [])], project, limit=6000)


def check_project(project: Path, style: bool = False) -> str:
    """--review: the project is the person's, so the output ends with what a review reports, without the
    parameters the editor fills and the next steps of writing a project."""
    return run_script("check_project", ["--review", *(["--style"] if style else [])], project, limit=6000)


def edit_sheet(project: Path, sheet: str, plan: list | str, new: bool = False) -> tuple[bool, str]:
    """Check the plan with --dry-run, then write it and run the checker; return whether it was written."""
    text = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
    flags = ["--new"] if new else []
    with tempfile.TemporaryDirectory() as tmp:
        plan_file = Path(tmp) / "plan.json"
        plan_file.write_text(text, encoding="utf-8")
        code, out = run_script_code("edit_sheet", [sheet, str(plan_file), "--dry-run", *flags], project)
        if code != 0:
            return False, out + "\n-- refused; fix the plan as the lines above say and call edit_sheet again"
        edits.snapshot(project)
        code, out = run_script_code("edit_sheet", [sheet, str(plan_file), *flags], project)
    if code != 0:
        edits.drop_snapshot(project)
        return False, out
    out = re.sub(r"\nnote: if the project is open in the Construct 3 editor[^\n]*", "", out)  # not the person's editor
    return True, out + "\n-- written. check_project now:\n" + check_project(project)


def edit_call(sheet, plan, new, arguments) -> dict:
    """The edit_sheet call, also when the model wrapped a long one as {"arguments": "<the call as text>"}
    (2026-10-06: eight of fourteen calls of one conversion came so)."""
    if arguments is not None:
        inner = newproject.unwrap(arguments, "")
        if not isinstance(inner, dict):
            raise TypeError("the call's arguments are not valid JSON; send sheet, plan and new as the call's own keys")
        sheet, plan, new = inner.get("sheet", sheet), inner.get("plan", plan), inner.get("new", new)
    if not sheet or plan is None:
        raise TypeError("edit_sheet needs sheet (the sheet's name) and plan (the list of operations)")
    return {"sheet": sheet, "plan": plan, "new": bool(new)}


def undo_edit(project: Path, all: bool = False) -> tuple[bool, str]:
    if not edits.edit_count(project):
        return False, "no edit to undo: the project is as the person sent it"
    left = edits.undo(project, everything=all)
    return left > 0, (f"undone; {left} edit(s) remain, the project with them is sent after the reply" if left
                      else "undone; the project is again as the person sent it, so no file is sent")


def read_script(project: Path, path: str, first: int = 1, last: int = 200) -> str:
    """Lines first to last of a file under the project's scripts folder, numbered."""
    root = (project / "scripts").resolve()
    target = (project / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        files = [f.relative_to(project).as_posix() for f in root.rglob("*") if f.is_file()] if root.is_dir() else []
        return f"no script {path!r}; scripts: {', '.join(files) or 'none'}"
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    part = lines[max(first, 1) - 1 : last]
    more = f"\n-- {len(lines)} lines; read on with first={last + 1}" if last < len(lines) else ""
    hint = ("\n-- before calling an API in this file wrong, missing or uncertain, look it up with "
            "lookup_script_api(name); report only what the lookup shows")
    return "\n".join(f"{n:>4} {line}" for n, line in enumerate(part, start=max(first, 1))) + more + hint


def project_handlers(project: Path, changed, send_project) -> dict:
    """The handlers of PROJECT_TOOLS bound to one project. changed(result) records whether an edit or undo
    left the project to be sent; send_project is the answer's own, since it knows what was made."""
    return {
        "lookup_ace": lambda object, words=None: lookup_ace(object, words, project),
        "print_sheet": lambda **kw: print_sheet(project, **kw),
        "print_layout": lambda layouts=None, layer=None: print_layout(project, layouts, layer),
        "check_project": lambda **kw: check_project(project, **kw),
        "read_script": lambda path, first=1, last=200: read_script(project, path, first, min(last, first + 199)),
        "edit_sheet": lambda sheet=None, plan=None, new=False, arguments=None: changed(
            edit_sheet(project, **edit_call(sheet, plan, new, arguments))),
        "undo_edit": lambda all=False: changed(undo_edit(project, all)),
        "send_project": send_project,
    }
