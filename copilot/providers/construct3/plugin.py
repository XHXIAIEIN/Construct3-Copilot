"""The Construct 3 knowledge plugin: what the bot knows about Construct 3 and how it checks an answer.

The host agent loop consumes these tools, callbacks and validation rules:

- TOOLS, HANDLERS: the tools every question gets, and the functions behind them
- PROJECT_TOOLS, PROJECT_PROMPT, project_handlers(project, changed, send_project): the tools a sent project adds
- VOICE_PROMPT: how every reply reads
- GROUP_PROMPT: the note for a message from a group
- session_tools(run): the tools, handlers and extra steps for making a new project in run.session
- presearch(question): the search words for a question, or None, and the tool call that holds its result
- check(messages, text, project, ask_json): the names the text uses that the knowledge does not hold
- BUSY: the note sent at the first tool call that makes or changes a project
- tool_trace(name, arguments, result): the trace line of one tool call
- mend_arguments(name, arguments): the JSON of a call whose arguments did not parse, or None
- is_new(project), runtime_verified(project), pack(project): project origin, editor evidence and prepared archive
- left_for_later(session): what the design kept for a new project leaves out of the request
- CHECK_FAILED, PROJECT_STEPS: the message after a failed check, the extra steps a sent project allows
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Callable

from . import edits
from .services import LOCALE, RAG

from . import newproject
from .acecheck import LIST_ACES, missing_aces, project_text
from .tools import (GROUP_PROMPT, HANDLERS, PROJECT_PROMPT, PROJECT_TOOLS, TOOLS, VOICE_PROMPT,  # noqa: F401
                    project_handlers, run_script)

log = logging.getLogger("copilot.construct3")

PROJECT_STEPS = 6  # a change reads the sheet, looks its ACEs up and may send a plan twice
# the note sent before the reply when a tool starts to make or change a project, so the person knows the bot is
# busy and not stuck (2026-10-06); a making run takes two to four minutes, an edit about one
BUSY = {"design_guide": "在做了，要两三分钟，做好发你。", "check_design": "在做了，要两三分钟，做好发你。",
        "new_project_from_spec": "在做了，要两三分钟，做好发你。", "new_project_from_template": "在做了，做好发你。",
        "edit_sheet": "在改了，改好发你。"}
PRESEARCH_MIN = 8  # characters; "在吗" or "做好了吗" asks nothing to search for
PRESEARCH = (
    "A Construct 3 user asks:\n{question}\n\nGive 2 to 5 short English search words for the Construct 3 features "
    "and the problem in this question (e.g. time scale, pause, animation, touch, layer). "
    'Set "show" to true when it asks how to make something a player sees or does (an effect, a motion, a '
    "mechanic) that takes several steps to build, so a small example project shows it better than words; false "
    "for a yes-or-no question, an expression, a setting, an error, or a question about the person's own project. "
    'Reply with JSON only: {{"words": ["...", "..."], "show": false}}'
)
CHECK_FAILED = (
    "Check failed: {missing}. A name the schema lacks may not exist, or may belong to another plugin or behavior. "
    "An object that is not a plugin or behavior is the problem, not its ACE names: look its ACEs up under the "
    "plugin or behavior it is an instance of, and keep the object's name in the answer. "
    "Look each one up with lookup_ace, then rewrite the whole answer for the user using only ACEs the lookups "
    "printed. Do not mention this check."
)
# the tools whose broken JSON is mended rather than refused: a spec breaks its brackets far from where the
# parser notices
MENDED_TOOLS = ("new_project", "check_design", "patch_spec")
MENDED_NOTE = ("-- the call's JSON had brackets out of order; they were closed where the next closer showed a list "
               "or object had ended. Check the build below as usual\n")
DESIGN_LINES = ('tests[', 'rules', 'state', 'inputs', 'design', 'ok:', 'refused', 'win', 'lose', 'reference', 'screen')
BUILD_TOOLS = ("new_project_from_", "check_design", "patch_spec")  # a trace that holds one tried to make a project

is_new = newproject.is_new
runtime_verified = newproject.runtime_verified
left_for_later = newproject.left_for_later


def pack(project: Path) -> Path:
    """The .c3p of the project as it is now: a made project or the person's edited one."""
    return newproject.pack(project, RAG) if newproject.is_new(project) else edits.pack(project, RAG)


def session_tools(run) -> tuple[list[dict], dict, int]:
    """The tools that make a new project in run.session, their handlers and the steps they add: a new game reads
    an example, sends its design two or three times, looks up a dozen ACEs and may send its spec three times."""
    session, trace, made = run.session, run.trace, run.made
    handlers = {
        "spec_guide": lambda: newproject.QUICK_GUIDE if newproject.QUICK else newproject.SPEC_GUIDE,
        "read_example": lambda id: newproject.read_example(
            id, RAG, LOCALE, sum(t.startswith("read_example") for t in trace)),
        "design_guide": lambda: newproject.design_guide(RAG),
        "check_design": lambda design=None, arguments=None: newproject.check_design(
            design if design is not None else newproject.unwrap(arguments, "design"), session, RAG,
            any(t.startswith("read_example") for t in trace)),
        # after a JSON error the model sometimes wraps the whole call in {"arguments": "<the call as a string>"}
        # keys of the spec sent beside it ("viewport", 2026-10-04) go into it
        "new_project_from_spec": lambda spec=None, arguments=None, **rest: made(newproject.from_spec(
            newproject.gather(spec if spec is not None or rest else newproject.unwrap(arguments), rest),
            session, RAG, LOCALE)),
        "patch_spec": lambda changes=None, arguments=None: made(newproject.patch_spec(
            changes if changes is not None else newproject.unwrap(arguments, "changes"), session, RAG, LOCALE)),
        "new_project_from_template": lambda template_id, name: made(
            newproject.from_template(template_id, name, session, RAG, LOCALE)),
    }
    tools = newproject.QUICK_TOOLS if newproject.QUICK else newproject.TOOLS
    return list(tools), handlers, 20 if newproject.QUICK else 48


def session_prompt() -> str:
    return newproject.prompt()


def presearch(question: str, ask_json: Callable[[list[dict]], dict]) -> tuple[list[str], str, bool] | str:
    """The pitfall search for a question before the model answers: the words, the search result and whether an
    example shows the answer better than words, or the trace line that says why there was none. ask_json(messages)
    is one model call that answers a JSON object.

    2026-10-09: asked how to pause a battle while an ultimate animation plays, the model guessed ACE names three
    times and gave up without one search, though wait-and-time-scale.md holds the answer; a tool result steers
    a small model where the prompt's "call it for every how-to question" did not."""
    if len(question) < PRESEARCH_MIN:
        return ""
    try:
        found = ask_json([{"role": "user", "content": PRESEARCH.format(question=question[:1000])}])
        words = [str(w) for w in found.get("words", [])][:6]
        show = found.get("show") is True
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        return f"presearch: no words ({type(e).__name__})"
    if not words:
        return "presearch: no words"
    try:
        out = run_script("search_guides", [*words, "--examples", "0", "--pitfalls", "3"], limit=5000)
    except subprocess.TimeoutExpired:
        return "presearch: search timed out"
    return words, out, show


PRESEARCH_TOOL = "search_guides"


def check(messages: list[dict], text: str, project: Path | None, ask_json: Callable[[list[dict]], dict]) -> list[str]:
    """The ACEs the text names that no lookup prints; empty when the answer passes."""
    try:
        aces = ask_json([*messages, {"role": "assistant", "content": text},
                         {"role": "user", "content": LIST_ACES}]).get("aces", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning("ACE list unreadable: %s", exc)
        return ["ACE validation result unreadable"]
    if not isinstance(aces, list):
        return ["ACE validation result must be a list"]
    return missing_aces(aces, project, project_text(messages))


def mend_arguments(name: str, arguments: str) -> tuple[dict, str] | None:
    """For a build tool whose arguments did not parse: the arguments with their brackets put in order, and the
    note that tells the model so. None for any other tool: its error goes back as it is."""
    if not name.startswith(MENDED_TOOLS):
        return None
    return json.loads(newproject.mend(newproject.balance(arguments))), MENDED_NOTE


def tool_trace(name: str, arguments: str, result: str) -> str:
    """The trace line of one tool call. The log keeps what an edit or a build did, to find refusals that do not
    steer the model."""
    line = f"{name}({arguments})"
    if name in ("edit_sheet", "undo_edit"):
        line += f" -> {result.splitlines()[0][:200]}"
    if name.startswith(("new_project", "patch_spec")):
        line += f" -> {' / '.join(result.splitlines()[:4])[:600]}"
    if name == "check_design":
        line += f" -> {' / '.join(l for l in result.splitlines() if l.startswith(DESIGN_LINES))[:900]}"
    return line
