"""Construct 3 answer agent: DeepSeek with two lookup tools over a Construct3-RAG clone."""
from __future__ import annotations

import difflib
import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from openai import BadRequestError, OpenAI

import edits
import gpu_yield
import newproject

log = logging.getLogger("c3bot.agent")

RAG = Path(os.environ.get("CONSTRUCT3_RAG", r"D:\Users\Administrator\Documents\GitHub\Construct3-RAG"))
LOCALE = os.environ.get("C3BOT_LOCALE", "zh-CN")
# C3BOT_BASE_URL points at any OpenAI-compatible server, e.g. Ollama's http://localhost:11434/v1
BASE_URL = os.environ.get("C3BOT_BASE_URL", "https://api.deepseek.com")
SILICONFLOW = "siliconflow" in BASE_URL  # hosted Chinese models, for comparison runs (2026-10-09)
ZHIPU = "bigmodel.cn" in BASE_URL  # glm-4.7-flash, free (2026-10-09)
LOCAL = "api.deepseek.com" not in BASE_URL and not SILICONFLOW and not ZHIPU
MODEL = os.environ.get("C3BOT_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TIMEOUT = 600 if LOCAL else 300 if SILICONFLOW or ZHIPU else 120  # a local model reads a long prompt slowly
# thinking off: DeepSeek reads "thinking", Ollama reads reasoning_effort "none", SiliconFlow reads enable_thinking;
# C3BOT_EXTRA_BODY (JSON) replaces it for a model that wants another switch
NO_THINK = ({"reasoning_effort": os.environ.get("C3BOT_REASONING", "none"), "max_tokens": 6000} if LOCAL
            else {"enable_thinking": False, "max_tokens": 6000} if SILICONFLOW
            else {"thinking": {"type": "disabled"}, "max_tokens": 6000} if ZHIPU
            else {"thinking": {"type": "disabled"}})
if os.environ.get("C3BOT_EXTRA_BODY"):
    NO_THINK = json.loads(os.environ["C3BOT_EXTRA_BODY"])
MAX_STEPS = 10

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
]


def run_script_code(name: str, args: list[str], project: Path | None = None, limit: int = 6000,
                    locale: str = LOCALE) -> tuple[int, str]:
    """Run a script of the construct3-agent-plugin skill; return its exit code and what it printed."""
    script = RAG / "skills" / "construct3-agent-plugin" / "scripts" / f"{name}.py"
    cmd = [sys.executable, str(script), "--rag", str(RAG), "--locale", locale, "--limit", str(limit)]
    if project:
        cmd += ["--project", str(project)]
    proc = subprocess.run(cmd + args, capture_output=True, text=True, encoding="utf-8", timeout=90, cwd=Path(__file__).parent)
    return proc.returncode, (proc.stdout + proc.stderr).strip() or "no output"


def run_script(name: str, args: list[str], project: Path | None = None, limit: int = 6000, locale: str = LOCALE) -> str:
    """Run a script of the construct3-agent-plugin skill and return what it printed."""
    return run_script_code(name, args, project, limit, locale)[1]


def lookup_ace(object: str, words: list[str] | None = None, project: Path | None = None) -> str:
    return run_script("lookup_ace", [object, *(words or [])], project)


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


def add_system(messages: list[dict], text: str) -> None:
    """Add text to the system message; the message exists only once something is added to it."""
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] += "\n\n" + text.strip()
    else:
        messages.insert(0, {"role": "system", "content": text.strip()})


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


def print_sheet(project: Path, sheets: list[str] | None = None, events: str | None = None, outline: bool = False,
                show: int | None = None) -> str:
    args = [*(["--events", events] if events else []), *(["--outline"] if outline else []),
            *(["--show", str(show)] if show else []), *(sheets or [])]
    return run_script("print_sheet", ["--review", *args], project, limit=8000)


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


def lookup_script_api(name: str) -> str:
    """An interface with its members, or a member with its declaration: the RAG's lookup_script_api.py."""
    return run_script("lookup_script_api", [name])


def check_project(project: Path, style: bool = False) -> str:
    """--review: the project is the person's, so the output ends with what a review reports, without the
    parameters the editor fills and the next steps of writing a project."""
    return run_script("check_project", ["--review", *(["--style"] if style else [])], project, limit=6000)


def search_examples(words: list[str]) -> str:
    """The official examples that hold the words, "id: name. description", from the RAG's search_guides.py.
    The commands it prints under each one are left out: the bot reads an example with read_example."""
    out = run_script("search_guides", [*words, "--pitfalls", "0"])
    return "\n".join(line for line in out.splitlines() if line != "examples:" and not line.startswith("  "))


def search_guides(words: list[str]) -> str:
    """The pitfall entries that hold the words, each in full with its file and line: the RAG's search_guides.py."""
    return run_script("search_guides", [*words, "--examples", "0"])


TOOLS.append({
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
})

TOOLS.append({
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
})

HANDLERS = {
    "lookup_ace": lookup_ace,
    "search_examples": search_examples,
    "search_guides": search_guides,
    "lookup_script_api": lookup_script_api,
}

LIST_ACES = (
    "List every event-sheet condition, action or expression your last answer names. Leave out scripting API "
    "methods and properties (anything called from JavaScript, e.g. isMouseButtonDown, getAllInstances). "
    "Reply with JSON only: "
    '{"aces": [{"object": "8Direction", "name": "设置最大速度", "written_as": "action"}]}. object is System, a '
    "plugin or a behavior as lookup_ace takes it; name is the display name alone, without parameters or the "
    "object; written_as is how the answer uses it: condition (before the arrow), action (after the arrow) or "
    "expression (inside a parameter). "
    'An answer that names none gives {"aces": []}.'
)
MAX_CHECKS = 2
REPLY_MAX = 350  # characters; a longer answer is sent back once to be shortened
# the note sent before the reply when a tool starts to make or change a project, so the person knows the bot is
# busy and not stuck (2026-10-06); a making run takes two to four minutes, an edit about one
BUSY = {"design_guide": "在做了，要两三分钟，做好发你。", "check_design": "在做了，要两三分钟，做好发你。",
        "new_project_from_spec": "在做了，要两三分钟，做好发你。", "new_project_from_template": "在做了，做好发你。",
        "edit_sheet": "在改了，改好发你。"}
# a request for an example or a project file, in the words people use; the note sent with it routes the model to the
# project tools, since the prompt's own list of such requests steered it only sometimes (2026-10-06)
BUILD_ASK = re.compile(r"(?:做|制作|生成|重做|写)[^。！？\n]{0,40}(例子|示例|样例|demo|工程|项目|游戏|小游戏|原型)"
                       r"|(给我|发我|发给我|给我发|给个|来个|来一个|要个|要一个|整个|弄个|搞个|写个)[^。，\n]{0,12}"
                       r"(例子|示例|样例|demo|工程|项目|游戏|小游戏|原型)"
                       r"|example project|make (me )?(a|an) (example|demo|project)", re.I)
# a bare "c3p" or "工程文件" means the held project when one is held, a new one when none is
BUILD_ASK_BARE = re.compile(r"c3p|工程文件|项目文件", re.I)
BUILD_NOTE = ("\n(The person asks for an example or a project file: make it with the project tools (design_guide, "
              "check_design, new_project_from_spec) and it is sent after your reply. Words alone do not answer it.)")
PROMISE = re.compile(r"(文件|c3p|工程|项目|例子)[^。！\n]*((发|传)(给|到)?你|发送|发来|发出|稍后|随后)"
                     r"|(发|传)(给|到)?你[^。！\n]*(文件|c3p|工程|例子)")
SHORTEN = (
    "Rewrite your last answer in under {n} characters for the user. Keep the conclusion, the deciding reason and "
    "the steps the user must do, in everyday words. Keep the approach, not its details. Cut walkthroughs of what the code or events already do, second "
    "options, side notes, and code names, values and line numbers the person does not have to type. Keep every "
    "condition and action name the answer uses (e.g. 设置对象速率), copied exactly, since the person finds them "
    "in the editor by that name. Same language, plain text, no mention of this request."
)
PRESEARCH_MIN = 8  # characters; "在吗" or "做好了吗" asks nothing to search for
PRESEARCH = (
    "A Construct 3 user asks:\n{question}\n\nGive 2 to 5 short English search words for the Construct 3 features "
    "and the problem in this question (e.g. time scale, pause, animation, touch, layer). "
    'Reply with JSON only: {{"words": ["...", "..."]}}'
)
SENT_MAX = 100  # characters; the reply that goes out with a project file
SHORTEN_SENT = (
    "The project file is sent with this reply. Rewrite your last answer in under {n} characters: what the "
    "example shows and what to tap or press to see it, in one or two sentences. No explanation of the "
    "mechanism, the layout, event numbers or object names. Same language, plain text, no mention of this request."
)
EVENTS_MAX = 1000  # an answer that writes events the person asked for
ASKED_EVENTS = re.compile(r"事件|怎么写|写一下|写出来|写法|具体|步骤|example|event")
SHORTEN_EVENTS = (" Keep every event line (conditions, then → actions) exactly as written; shorten the words "
                  "around them.")


# phrases the prompt bans; a reply that still holds one loses that sentence before it is sent (2026-10-06)
BANNED = re.compile(r"希望(对你)?有(所)?帮助|很高兴|好问题|简单来说|本质上|值得注意的是|祝你|"
                    r"欢迎(再|继续|随时)|有(其他|别的|什么|任何)问题(可以|随时|再|欢迎)")
# a closing offer or question: dropped while it ends the reply and another sentence remains
OFFER = re.compile(r"需要|要不要|想不想|如果(你)?(需要|想|有)|还(需要|想要|有什么)|可以(帮你|给你|为你)|我可以|"
                   r"告诉我|说一声|说一句")


def scrub(text: str) -> tuple[str, str]:
    """Return the reply without banned phrases and closing offers, and a note of what was dropped."""
    parts = [p for p in re.split(r"(?<=[。！？!?\n])", text) if p]
    # a phrase that opens a sentence ("简单来说，加计时器") goes alone; a sentence built on one goes whole
    cut = [re.sub(r"^\s*(?:" + BANNED.pattern + r")\s*[，,、：:]\s*", "", p) for p in parts]
    kept = [p for p in cut if not BANNED.search(p) and re.search(r"[\w一-鿿]", p)]
    while len(kept) > 1 and OFFER.search(kept[-1]) and not re.search(r"c3p|\.zip|文件|项目|工程", kept[-1]):
        kept.pop()
    while kept and not kept[-1].strip():
        kept.pop()
    out = "".join(kept).strip()
    return (out if out else text), ("scrubbed" if out and out != text.strip() else "")


def _norm(s: str) -> str:
    return re.sub(r"[\s\"'“”‘’：:]", "", s).lower()


KINDS = ("condition", "action", "expression")


def _ace_lines(output: str, common: bool = True) -> dict[str, str]:
    """The ACE header lines of a lookup ('action wait - 等待 [system]') by kind, so a miss that echoes the word
    never matches. common=False drops the [_common] lines, which a System lookup prints as a hint although
    System has none of them."""
    lines: dict[str, list[str]] = {k: [] for k in KINDS}
    for line in output.splitlines():
        m = re.match(r"(condition|action|expression)\s", line)
        if m and (common or "[_common]" not in line):
            lines[m.group(1)].append(line)
    return {k: _norm("\n".join(v)) for k, v in lines.items()}


def _join(*parts: dict[str, str]) -> dict[str, str]:
    return {k: "".join(p[k] for p in parts) for k in KINDS}


PROJECT_READERS = ("print_sheet", "print_layout", "read_script", "check_project")


def project_text(messages: list[dict]) -> str:
    """What the tools printed from the person's own project, normalised: the names it uses are real there."""
    names = {c["id"]: c["function"]["name"] for m in messages if m.get("role") == "assistant"
             for c in m.get("tool_calls") or []}
    return _norm("\n".join(m.get("content") or "" for m in messages
                           if m.get("role") == "tool" and names.get(m.get("tool_call_id")) in PROJECT_READERS))


def _near(output: str, name: str) -> list[str]:
    """The display names of a full lookup closest to a guessed one: a Chinese name is one word to lookup_ace, so a
    near miss (设置时间比例 for 设置时间速率) finds nothing there (2026-10-09: three guesses, no lookup, no answer)."""
    names = re.findall(r"^(?:condition|action|expression)\s+\S+\s+(.+?)\s+\[", output, re.M)
    return difflib.get_close_matches(name, list(dict.fromkeys(names)), n=3, cutoff=0.4)


def missing_aces(aces: list[dict], project: Path | None = None, seen: str = "") -> list[str]:
    """Return 'object: name' for each named ACE that the object's full lookup does not print.

    seen is project_text(): a name the project's printed events or scripts hold is not checked, because a
    summary of a sent project names its variables, its addons' ACEs and actions with their parameters, which
    the schema lookup does not print (2026-10-04: fifty such names used up every step)."""
    cache: dict[str, dict[str, str]] = {}
    raw: dict[str, str] = {}  # the full lookups, for the closest names of a miss
    missing = []
    for ace in aces:
        obj, name = str(ace.get("object", "")), str(ace.get("name", ""))
        written = str(ace.get("written_as", ""))
        if not obj or not name:
            continue
        if seen and _norm(name) in seen:
            continue
        common = obj.lower() != "system"
        if obj not in cache:
            # the model may name an ACE in English as well as in the schema locale
            raw[obj] = (run_script("lookup_ace", [obj], project, limit=0) + "\n"
                        + run_script("lookup_ace", [obj], project, limit=0, locale="en-US"))
            cache[obj] = _ace_lines(raw[obj], common)
        found = cache[obj]
        if not any(_norm(name) in found[k] for k in KINDS):
            # a bare lookup leaves out the ACEs every world object shares (_common), so retry with the name as a word
            found = _join(found, _ace_lines(lookup_ace(obj, [name], project), common),
                          _ace_lines(run_script("lookup_ace", [obj, name], project, locale="en-US"), common))
        kinds = [k for k in KINDS if _norm(name) in found[k]]
        if not kinds:
            near = _near(raw[obj], name)
            missing.append(f"{obj}: {name}" + ("" if common else " (System has no such ACE; if every object has it, "
                                                                 "it belongs to the object itself, so name the object)")
                           + (f"; closest real names: {', '.join(near)}" if near else ""))
        elif written in KINDS and written not in kinds:
            # 2026-10-04: Pick top/bottom, a condition, was written after the arrow as if it were an action
            missing.append(f"{obj}: {name} is a {' or '.join(kinds)}, but the answer writes it as {'an' if written[0] in 'ae' else 'a'} {written}; "
                           "a condition goes before the arrow, an action after it")
    return missing


USAGE_LOG = Path(__file__).parent / "logs" / "bot" / "usage.log"  # one line an answer, QQ and --cli alike
_tally = threading.local()  # the token count of the answer this thread is giving


def write_usage(session: Path | None, tally: dict, seconds: float) -> None:
    """Terminal runs (--cli, specs/e2e.py) do not write bot.log, so every answer also goes to usage.log."""
    line = (f"{session.name if session else '-'} calls {tally['calls']} prompt {tally['prompt']} "
            f"(cache hit {tally['cache_hit']}) completion {tally['completion']} in {seconds:.0f} s")
    log.info("usage: %s", line)
    try:
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError as exc:
        log.warning("usage.log not written: %s", exc)


class Agent:
    def __init__(self, api_key: str) -> None:
        # the free glm-4.7-flash answers 429 "访问量过大" to about 5 calls in 8 (2026-10-09); the SDK backs off and retries
        self.client = OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=10 if ZHIPU else 2)
        create = self.client.chat.completions.create

        def counted(*args, **kwargs):
            # every model call of an answer, the tool loop's and the checks', adds to the thread's tally
            if LOCAL:  # the TTS server on the same GPU goes first (2026-10-09)
                gpu_yield.wait_for_tts(BASE_URL, MODEL)
            resp = create(*args, **kwargs)
            tally, usage = getattr(_tally, "now", None), getattr(resp, "usage", None)
            if tally is not None and usage is not None:
                tally["calls"] += 1
                tally["prompt"] += usage.prompt_tokens or 0
                tally["completion"] += usage.completion_tokens or 0
                tally["cache_hit"] += getattr(usage, "prompt_cache_hit_tokens", 0) or 0
            return resp

        self.client.chat.completions.create = counted

    def answer(
        self, question: str, history: list[dict] | None = None, project: Path | None = None, group: bool = False,
        outbox: list[Path] | None = None, session: Path | None = None, notify=None,
    ) -> tuple[str, list[str]]:
        """Return the reply and a trace of tool calls. With a project, its sheets and checker are tools too,
        and a project the answer changed, or was asked to send, is packed into outbox to go after the reply.
        With a session folder, a new project can be made there; it replaces the project and is sent."""
        trace: list[str] = []
        _tally.now = {"calls": 0, "prompt": 0, "completion": 0, "cache_hit": 0}
        started = time.monotonic()
        send = {"project": False}  # set by a written edit, an undo that leaves edits, send_project or a new project
        current = {"project": project}  # a new project replaces the one passed in
        edits_before = edits.edit_count(project) if project else 0

        def changed(result: tuple[bool, str]) -> str:
            send["project"] = send["project"] or result[0]
            return result[1]

        def send_project() -> str:
            # a model that cannot make the change sent the untouched project and said it had (script-only, 2026-10-04)
            project = current["project"]
            if project and newproject.is_new(project):
                send["project"] = True
                return "the project as it is now is sent as a file after the reply"
            if not (project and edits.edit_count(project)):
                return ("not sent: nothing in the project was changed, so the file would be the one the person sent. "
                        "Do not say a file was sent. If they asked for a change you did not make, tell them in words "
                        "what to change and where.")
            send["project"] = True
            return "the project as it is now is sent as a file after the reply"

        try:
            text = self._answer(question, history, project, group, trace, changed, send_project, session, current, send,
                                notify)
            tried = any(t.startswith(("new_project_from_", "check_design", "patch_spec")) for t in trace)
            made = send["project"] and newproject.is_new(current["project"])
            # a reply that describes a game and promises its file, with no build tried (quick mode, 2026-10-06)
            if (tried and (not made or "steps ran out" in trace)) or (session and not project and not made and PROMISE.search(text)):
                # the model said the game was made when every build had been refused (2026-10-04)
                text = "这个游戏这次没生成出来。把玩法说得再简单具体一点，再让我做一次。"
                # a build that failed its play test sits unmarked in the session folder; an edit_sheet on it then
                # packed and sent it as "-edited" beside this text (2026-10-06)
                send["project"] = False
        finally:
            project = current["project"]
            if project and newproject.is_new(project) and "steps ran out" in trace:
                send["project"] = False  # a game the answer did not finish is not sent as if it were
            elif project and "steps ran out" in trace and edits.edit_count(project) > edits_before:
                # a change left half done (a sheet with one variable, 2026-10-06) is taken back, not sent
                while edits.edit_count(project) > edits_before:
                    edits.undo(project)
                send["project"] = False
                text = "这次没改完，项目保持原样。分几步来：先说要先改哪一部分。"
                trace.append("unfinished edits undone")
            elif project and not send["project"] and edits.edit_count(project) > edits_before:
                while edits.edit_count(project) > edits_before:  # edits of a build that is not sent
                    edits.undo(project)
                trace.append("edits of an unsent build undone")
            if project and send["project"] and outbox is not None:
                try:
                    outbox.append(newproject.pack(project, RAG) if newproject.is_new(project) else edits.pack(project, RAG))
                    trace.append(f"packed {outbox[-1].name}")
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    log.warning("pack failed: %s", exc)
                    trace.append(f"pack failed: {exc}")
            write_usage(session, _tally.now, time.monotonic() - started)
            _tally.now = None
        if session and (BUILD_ASK.search(question) or (project is None and BUILD_ASK_BARE.search(question))) and not outbox:
            text = "这次没有生成可交付的工程文件，尚未完成你要的例子。"
            trace.append("requested file unavailable")
        if not send["project"]:
            kept = [s for s in re.split(r"(?<=[。！\n])", text) if not PROMISE.search(s)]
            if len(kept) < len(re.split(r"(?<=[。！\n])", text)):
                trace.append("promise of a file dropped")
                text = "".join(kept).strip()
        text, note = scrub(text)
        if note:
            trace.append(note)
        return text, trace

    def _presearch(self, messages: list[dict], question: str, trace: list[str]) -> None:
        """Search the pitfalls before the model answers and put the result in as its own search_guides call.

        2026-10-09: asked how to pause a battle while an ultimate animation plays, the model guessed ACE names three
        times and gave up without one search, though wait-and-time-scale.md holds the answer; a tool result steers
        a small model where the prompt's "call it for every how-to question" did not."""
        if len(question) < PRESEARCH_MIN:
            return
        try:
            found = self._json([{"role": "user", "content": PRESEARCH.format(question=question[:1000])}])
            words = [str(w) for w in found.get("words", [])][:6]
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            trace.append(f"presearch: no words ({type(e).__name__})")
            return
        if not words:
            trace.append("presearch: no words")
            return
        try:
            out = run_script("search_guides", [*words, "--examples", "0", "--pitfalls", "3"], limit=5000)
        except subprocess.TimeoutExpired:
            trace.append("presearch: search timed out")
            return
        call = {"id": "presearch", "type": "function",
                "function": {"name": "search_guides", "arguments": json.dumps({"words": words})}}
        messages.append({"role": "assistant", "content": "", "tool_calls": [call]})
        messages.append({"role": "tool", "tool_call_id": "presearch", "content": out})
        trace.append(f"presearch {words}")

    def _answer(self, question, history, project, group, trace, changed, send_project, session=None, current=None,
                send=None, notify=None) -> str:
        told = []  # the note sent once, at the first tool call that makes or changes a project
        asked = project is not None or bool(ASKED_EVENTS.search(question))  # events may make the reply longer
        if session is not None and (BUILD_ASK.search(question) or project is None and BUILD_ASK_BARE.search(question)):
            question += BUILD_NOTE
            trace.append("build ask")
        tools = list(TOOLS)
        handlers = dict(HANDLERS)
        steps = MAX_STEPS
        messages = [*(history or []), {"role": "user", "content": question}]
        if group:
            add_system(messages, GROUP_PROMPT)
        self._presearch(messages, question, trace)

        def use_project(project: Path) -> None:
            if "print_sheet" not in handlers:
                add_system(messages, PROJECT_PROMPT)
                tools.extend(PROJECT_TOOLS)
            handlers["lookup_ace"] = lambda object, words=None: lookup_ace(object, words, project)
            handlers["print_sheet"] = lambda **kw: print_sheet(project, **kw)
            handlers["print_layout"] = lambda layouts=None, layer=None: run_script(
                "print_layout", [*(layouts or []), *(["--layer", layer] if layer else [])], project, limit=6000)
            handlers["check_project"] = lambda **kw: check_project(project, **kw)
            handlers["read_script"] = lambda path, first=1, last=200: read_script(project, path, first, min(last, first + 199))
            handlers["edit_sheet"] = lambda sheet=None, plan=None, new=False, arguments=None: changed(
                edit_sheet(project, **edit_call(sheet, plan, new, arguments)))
            handlers["undo_edit"] = lambda all=False: changed(undo_edit(project, all))
            handlers["send_project"] = send_project

        def made(result: tuple[Path | None, str]) -> str:
            # a new project is the person's from here on: its tools replace the old project's, and it is sent
            if result[0]:
                current["project"] = result[0]
                send["project"] = True
                use_project(result[0])
            return result[1]

        if project:
            steps += 6  # a change reads the sheet, looks its ACEs up and may send a plan twice
            use_project(project)
        if session:
            add_system(messages, newproject.prompt())
            tools.extend(newproject.QUICK_TOOLS if newproject.QUICK else newproject.TOOLS)
            # a new game reads an example, sends its design two or three times, looks up a dozen ACEs and may send
            # its spec three times
            steps += 20 if newproject.QUICK else 48
            handlers["spec_guide"] = lambda: newproject.QUICK_GUIDE if newproject.QUICK else newproject.SPEC_GUIDE
            handlers["read_example"] = lambda id: newproject.read_example(
                id, RAG, LOCALE, sum(t.startswith("read_example") for t in trace))
            handlers["design_guide"] = lambda: newproject.design_guide(RAG)
            handlers["check_design"] = lambda design=None, arguments=None: newproject.check_design(
                design if design is not None else newproject.unwrap(arguments, "design"), session, RAG,
                any(t.startswith("read_example") for t in trace))
            # after a JSON error the model sometimes wraps the whole call in {"arguments": "<the call as a string>"}
            # keys of the spec sent beside it ("viewport", 2026-10-04) go into it
            handlers["new_project_from_spec"] = lambda spec=None, arguments=None, **rest: made(newproject.from_spec(
                newproject.gather(spec if spec is not None or rest else newproject.unwrap(arguments), rest),
                session, RAG, LOCALE))
            handlers["patch_spec"] = lambda changes=None, arguments=None: made(newproject.patch_spec(
                changes if changes is not None else newproject.unwrap(arguments, "changes"), session, RAG, LOCALE))
            handlers["new_project_from_template"] = lambda template_id, name: made(
                newproject.from_template(template_id, name, session, RAG, LOCALE))
        checks = 0
        draft = ''  # the last answer written, sent when the steps run out
        for _ in range(steps + MAX_CHECKS):
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                extra_body=NO_THINK,
                timeout=TIMEOUT,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                # check the model's own answer, then shorten it: a rewrite for length renames ACEs
                # (2026-10-09: 设置对象速率 came back as 设定对象时间速率), so a short version that fails the
                # check is dropped for the checked long one
                text = html.unescape((msg.content or "").strip())
                draft = text
                missing = self._check(messages, text, project)
                if not missing:
                    short = self._shorten(messages, text, trace, asked, sent=bool(send and send["project"]))
                    if short == text or not self._check(messages, short, project):
                        return short
                    trace.append("short version failed the check; long one sent")
                    return text
                if checks >= MAX_CHECKS:
                    trace.append(f"check: still missing {missing}")
                    return "这个我没把握写对，先不给步骤，免得你照着做却在编辑器里找不到对应的条件或动作。"
                checks += 1
                trace.append(f"check: missing {missing}")
                messages.append({"role": "assistant", "content": text})
                messages.append({
                    "role": "user",
                    "content": (
                        "Check failed: "
                        + "; ".join(missing)
                        + ". A name the schema lacks may not exist, or may belong to another plugin or behavior. "
                        "Look each one up "
                        "with lookup_ace, then rewrite the whole answer for the user using only ACEs the lookups "
                        "printed. Do not mention this check."
                    ),
                })
                continue
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                try:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        mended = ""
                    except json.JSONDecodeError:
                        if not call.function.name.startswith(("new_project", "check_design", "patch_spec")):
                            raise
                        # a spec breaks its brackets far from where the parser notices; put them in order and let
                        # the build check what the spec now says
                        args = json.loads(newproject.mend(newproject.balance(call.function.arguments)))
                        mended = ("-- the call's JSON had brackets out of order; they were closed where the next "
                                  "closer showed a list or object had ended. Check the build below as usual\n")
                    if notify and not told and call.function.name in BUSY:
                        told.append(call.function.name)
                        notify(BUSY[call.function.name])
                    result = handlers[call.function.name](**args)
                    result = mended + result if mended else result
                except json.JSONDecodeError as exc:
                    # a long call breaks its JSON somewhere in the middle; the position alone does not show where
                    log.warning("tool %s failed: %s", call.function.name, exc)
                    text = exc.doc or ""
                    before = text[max(0, exc.pos - 120):exc.pos]
                    stray = re.search(r'\}\s*,\s*"([^"]+)"\s*$', before)
                    hint = (f'the key "{stray.group(1)}" stands outside any object: the object before it closed too '
                            f'early, or it needs an object of its own; a block is one object {{"eventType": "block", '
                            f'"conditions": [...], "actions": [...]}} and its comment the object before it' if stray else
                            'count the brackets before this spot; a quote inside a string is written \\"')
                    result = (f"tool error: the call's arguments are not valid JSON: {exc.msg} at character {exc.pos}, "
                              f"here: {before}<<HERE>>{text[exc.pos:exc.pos + 60]}. {hint}. Send the whole call again "
                              "with that spot fixed")
                except (KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
                    log.warning("tool %s failed: %s", call.function.name, exc)
                    result = f"tool error: {exc}"
                trace.append(f"{call.function.name}({call.function.arguments})"
                             # the log keeps what an edit did, to find refusals that do not steer the model
                             + (f" -> {result.splitlines()[0][:200]}" if call.function.name in ("edit_sheet", "undo_edit") else "")
                             + (f" -> {' / '.join(result.splitlines()[:4])[:600]}" if call.function.name.startswith(("new_project", "patch_spec")) else "")
                             + (f" -> {' / '.join(l for l in result.splitlines() if l.startswith(('tests[', 'rules', 'state', 'inputs', 'design', 'ok:', 'refused', 'win', 'lose', 'reference', 'screen')))[:900]}"
                                if call.function.name == "check_design" else ""))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        trace.append("steps ran out")
        return "这次没有完成核实，暂时不能给你可直接照做的步骤。"

    def _shorten(self, messages: list[dict], text: str, trace: list[str], asked: bool = False,
                 sent: bool = False) -> str:
        # A reply sent with a project only says what to try in it; the person reads the events in the file
        # (2026-10-09: a 330-character delivery explained the mechanism, the layout and the event numbers).
        if sent:
            if len(text) <= SENT_MAX:
                return text
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=[*messages, {"role": "assistant", "content": text},
                          {"role": "user", "content": SHORTEN_SENT.format(n=SENT_MAX)}],
                extra_body=NO_THINK,
                timeout=TIMEOUT,
            )
            short = html.unescape((resp.choices[0].message.content or "").strip())
            trace.append(f"shortened {len(text)} -> {len(short)} (sent)")
            return short if short and len(short) < len(text) else text
        # Events are what the person copies: an answer that writes them may be longer, and a shortening keeps them
        # (2026-10-06: a 1414-character answer of events came back as 271 characters of prose without one).
        # three or more event lines; one arrow in prose does not make an answer of events (2026-10-06)
        # and only when the person asked for events or sent a project; a how-to question gets the approach
        events = asked and sum("→" in line for line in text.splitlines()) >= 3
        limit = EVENTS_MAX if events else REPLY_MAX
        if len(text) <= limit:
            return text
        resp = self.client.chat.completions.create(
            model=MODEL,
            messages=[*messages, {"role": "assistant", "content": text},
                      {"role": "user", "content": SHORTEN.format(n=limit) + (SHORTEN_EVENTS if events else "")}],
            extra_body=NO_THINK,
            timeout=TIMEOUT,
        )
        short = html.unescape((resp.choices[0].message.content or "").strip())
        if short and len(short) > limit:  # a first rewrite often stops short of the limit (1017 -> 889 at 350)
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=[*messages, {"role": "assistant", "content": short},
                          {"role": "user", "content": f"Still {len(short)} characters. " + SHORTEN.format(n=limit)
                           + " Drop every detail that is not the approach or a step the person must do."}],
                extra_body=NO_THINK,
                timeout=TIMEOUT,
            )
            again = html.unescape((resp.choices[0].message.content or "").strip())
            if again and len(again) < len(short):
                short = again
        trace.append(f"shortened {len(text)} -> {len(short)}")
        return short if short and len(short) < len(text) else text

    def _json(self, messages: list[dict]) -> dict:
        """One call that answers a JSON object. JSON mode where the model has it; Step-3.5-Flash on SiliconFlow
        refuses it ("Json mode is not supported", 2026-10-09), so then the object is cut out of plain text."""
        ask = dict(model=MODEL, messages=messages, extra_body=NO_THINK, timeout=TIMEOUT)
        try:
            resp = self.client.chat.completions.create(response_format={"type": "json_object"}, **ask)
        except BadRequestError:
            resp = self.client.chat.completions.create(**ask)
        text = resp.choices[0].message.content or ""
        return json.loads(text[text.find("{"):text.rfind("}") + 1] or "{}")

    def _check(self, messages: list[dict], text: str, project: Path | None = None) -> list[str]:
        try:
            aces = self._json([*messages, {"role": "assistant", "content": text},
                               {"role": "user", "content": LIST_ACES}]).get("aces", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            log.warning("ACE list unreadable: %s", exc)
            return ["ACE validation result unreadable"]
        if not isinstance(aces, list):
            return ["ACE validation result must be a list"]
        return missing_aces(aces, project, project_text(messages))
