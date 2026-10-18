"""A new Construct 3 project for a chat session: built from a spec by spec_build.py, or copied from an official template.

The project replaces the session folder, as an uploaded project does. A marker under sessions/_new/ records that
the bot made it, with the project's uniqueId, so that send_project sends it although no edit changed it, and so
that a project uploaded later to the same folder is not taken for it.

Copying a template is off unless template_copy is enabled: the license of Construct-Example-Projects allows the
examples inside a game made with Construct, not handed out as project files.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import string
import subprocess
import sys
import threading
from pathlib import Path

from . import services as copilot, edits
from . import quick_fix
from .services import DATA, RAG

log = logging.getLogger("copilot.construct3.newproject")

HERE = Path(__file__).parent
MARKS = DATA / "sessions" / "_new"
EXAMPLES = copilot.examples_root()
TEMPLATE_COPY = bool(copilot.OPTIONS.get("template_copy"))
SPEC_MAX = 60_000          # characters, as spec_build.py caps it
BUILD_TIMEOUT = 150        # seconds for one spec_build.py run: the build, edit_sheet.py and check_project.py
# The checker passes what the editor refuses (an empty expression parameter, 2026-10-04), so a built project is
# opened in the headless editor and the design's tests played on it before it is sent; editor_check=False skips it on a machine
# without Edge or Chrome. One run at a time: they share the browser profile.
# quick prototype: the spec format in the prompt, new_project_from_spec, no design check or editor play; for a slow local model
QUICK = bool(copilot.OPTIONS.get("quick"))
EDITOR_CHECK = bool(copilot.OPTIONS.get("editor_check", True))
PLAY_TIMEOUT = 240         # seconds for play_design.py: one editor session, a preview per test, 20 to 40 s
# the editor's browser profile; a second bot process, such as a test run beside the live bot, needs its own
PROFILE = Path(copilot.OPTIONS.get("profile") or MARKS / "profile")
_editor = threading.Lock()

SPEC_GUIDE = """A spec is JSON. Unknown keys are refused. Sizes and places are in grid units (32 px; 8 px when the
viewport is 360 high or less). Colours are roles: canvas, canvas_alt (the backdrop), solid (shapes), dim
(secondary text), ink (text, outlines), reward (yellow), danger (red), good (green), grey (off, idle), flash
(white), or your own under "palette";
the theme decides what each role looks like.

{"name": "Tap Dots",                       project name, up to 40 characters
 "viewport": [480, 854],                   optional, default [720, 1280]; portrait when higher than wide
 "theme": "day",                           greybox (greys, the default), day (light, blue shapes), night (dark,
                                           bright shapes), candy (pink, raspberry shapes)
 "palette": {"wood": [222, 184, 135]},     optional extra colour roles
 "primary": "Dot",                         optional: the Sprite the player looks at; nothing else may stand out more
 "objects": [
  {"name": "Dot", "plugin": "Sprite", "shape": "circle", "size": [2, 2], "frames": ["reward"],
   "outline": 2, "outline_color": "ink", "shadow": 3, "behaviors": ["Tween"], "variables": {"points": 1}},
      shape rect|circle|triangle|grid; grid draws a board: lines through the middle of each unit, so a piece
      placed on a unit sits on a crossing (Go, gomoku), its frame the board's colour, its lines outline_color;
      size [w, h] units, or "fill" for the screen's one main shape, as large as the stage allows (not the whole screen); frames: one
      colour per animation frame, one per state (off, on), chosen in events with Sprite "Set frame" (frame 0
      first), never Set color, which darkens a coloured image; outline and shadow: true, false or px, by default thin and
      sized to the shape; a board of cells is cells with "outline": 1 in a darker role; behaviors: Tween, Timer, Solid,
      Sine, Bullet, 8Direction, Platform, MoveTo, Rotate, DragDrop, ScrollTo, DestroyOutsideLayout,
      BoundToLayout, or {"name": "Bullet", "properties": {"speed": 600}}; variables: name -> start value
  {"name": "Score", "plugin": "Text"},
  {"name": "Hp", "plugin": "Bar", "size": [6, 1], "frames": ["danger"]},   a generator component, NOT a native plugin: Hp and HpFrame become NinePatch objects.
      Set Hp width from the health ratio; look up NinePatch actions, never Bar actions
  {"name": "Grid", "plugin": "Array", "size": [10, 10]},     Array cells start at 0; Grid.At(x, y)
  {"name": "Touch", "plugin": "Touch"}                       also Mouse, Keyboard, Dictionary
 ],
 "layouts": [{"name": "Game", "sheet": "Game",
   "layers": [{"name": "Background", "color": "canvas"}, {"name": "Game"}, {"name": "UI", "parallax": 0}],
   "instances": [
    The screen is bands: "title" at the top, "status" under it (score, time), "stage" in the middle where the
    game is, "hint" at the bottom (what to do). The build places and sizes everything in them.
    {"object": "Dot", "layer": "Game", "col": 2, "row": 6, "repeat": [3, 1], "gap": 1, "index": ["points"]},
        a Sprite's top-left corner on grid cell (col, row), "col": "center" centres it, or its whole repeat,
        in the stage (the play area goes there), while its X and Y in events are its centre, so
        a piece created at Cell.X, Cell.Y sits in the middle of that Cell; repeat [cols, rows] places copies side by side,
        gap units apart; index names up to two variables that get each copy's column and row from 0;
        "frame": 1 starts on another frame; "visible": false for an invisible tap target over board cells (a tap anywhere on the screen is {"tap": [x, y]}, no object);
        "variables": {...} sets this instance's values
    {"object": "Button", "layer": "UI", "col": "center", "row": "center", "label": "Restart"}
        a button: the label is drawn on the Sprite by the Text ButtonLabel (Set text on ButtonLabel changes
        it), which moves, hides and is destroyed with the Sprite; the build sizes the Sprite to its label
    {"object": "Score", "layer": "UI", "text": "Score: 0", "band": "status", "align": "left", "longest": "Score: 999"}
        a Text in a band (title, status, stage, hint) at its left, center or right, as wide as "longest";
        "below": "Board" or "above": "Board" centres it one unit under or over a Sprite; "anchor" (top-left,
        top, bottom ...) picks the band on that edge; "color" and "on" (the role behind it)
    {"object": "Hp", "layer": "UI", "band": "status", "align": "right", "label": "HP"}
        a bar with its name in front of it
    A layout larger than the viewport is "screen": "free": a Text there takes "anchor", or "col", "row",
    "width", "height" and "align" in units
   ]}],
 "sheets": [{"name": "Game", "events": [
   {"eventType": "comment", "text": "Tap Dots. Tap a dot to score its points"},
   {"eventType": "variable", "name": "score", "type": "number", "initialValue": "0", "comment": "Points so far"},
   {"eventType": "comment", "text": "A tapped dot scores and disappears"},
   {"eventType": "block",
    "conditions": [{"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Dot", "type": "start"}}],
    "actions": [{"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "score", "value": "Dot.points"}},
                {"id": "set-text", "objectClass": "Score", "parameters": {"text": "\\"Score: \\" & score"}},
                {"id": "destroy", "objectClass": "Dot"}]}]}]}

Events are written as edit_sheet takes them: every condition and action is the write: line of lookup_ace with
<object> replaced by the spec's object name, <behavior name on the object> by the behavior's name, and "sid"
left out. Look each one up before writing it. Every top-level block has a comment right above it. Sub-events go
under "children"; {"eventType": "group", "title": "...", "children": [...]} groups them. An object with no
instance in any layout gets one in a layout "Objects" that never runs, so events can create it.
Before the project exists, lookup_ace takes plugins and behaviors (System, Sprite, Text, Array, Touch, Tween),
not the names in your spec. Every event that reacts to input has its trigger as the first condition: an event
without a trigger runs every tick. Touch also fires for the mouse, so input is Touch alone. Loops (For, For
each, Repeat, While) are conditions of a block, never actions: the actions they repeat are that block's actions.

The spec builds the design check_design passed, and the build plays that design's tests in the editor:
- One top-level event per rule, in the design's order, its comment starting with the rule's id ("place: ...");
  a sub-rule is a sub-event under "children", "else": true a System "else" condition first in its sub-event.
- Each state row where its stored_in says: "global" is {"eventType": "variable", "name": <name>, "type": "number"
  or "string", "initialValue": <start as text>} at the top of the sheet; "Array" an Array object of that name
  and size; "Obj.var" a variable of Obj, its instance starting at start; "Obj.text" the Text's instance with
  "text": start; "Obj.x"/"Obj.y" its instance placed there; "Obj.shown" (or "Obj.shown(frame=1)") no variable:
  the count is the Obj instances visible (on frame 1), as many as start on the layout, so "stones += 1" is
  System Create object Obj (a piece created at Cell.X, Cell.Y), or Set visible on the one Obj the event picked;
  an action on Obj with no pick of the one instance changes every Obj.
- Triggers: "start" System On start of layout; "tick" no trigger; "every N" System Every N seconds; an input
  {"tap": "Cell", "args": {"c": "col"}} Touch On touched Cell (type start), the argument read as Cell.col;
  {"tap": [x, y]} Touch On any touch start (never On tap), and with "region": [x0, y0, x1, y1] Compare two
  values on Touch.X and Touch.Y against OriginalViewportWidth * x0 ... after it; {"key": K} Keyboard On key
  pressed. On any touch start fires for every tap, a tap on an object too, before On touched.
- Effects: name = expr is Set value, Set text, Set instance variable or Set X by where name is stored;
  Grid.At(x, y) = v is Array Set value at XY; wait N is System Wait; restart is System Restart layout.
- InARow(Grid, n, v) of the design is the event kind {"eventType": "n-in-a-row", "array": "Grid", "count": n,
  "value": "v", "actions": [...]}: the builder writes the loops over the Array that test every line of n cells,
  across, down and on both diagonals; its actions run when one holds. Put it first among the sub-events of the
  event that writes the cell, the rule's other cases after it as "else".

A board of crossings (gomoku, go) or cells (tic-tac-toe): a grid object Board of the board's size in units, a
Sprite Cell of size [1, 1] with variables {"col": 0, "row": 0}, the piece, a circle of size [1, 1] with one frame
per side and no instance, an Array of the board's size. Instances, as written here:
  {"object": "Board", "layer": "Game", "col": "center", "row": "center"},
  {"object": "Cell", "layer": "Game", "over": "Board", "index": ["col", "row"]},
  {"object": "Title", "layer": "UI", "text": "...", "band": "title"},
  {"object": "Status", "layer": "UI", "text": "...", "longest": "...", "below": "Board"}
"over" lays one invisible Cell on every crossing, numbered by col and row; a piece is created at Cell.X, Cell.Y.

Keep it to one layout and one sheet unless the game needs more. Look: a theme; the play area at "col": "center",
"row": "center"; the game's name in the title band, what the player watches in status, what to do in hint; a button
is a Sprite with a "label"; a state that shows is a frame of its own."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_example",
            "description": (
                "Read the event sheets of an official example project (an id from search_examples) as the editor "
                "words them, to see how a game of this kind is built. Read only; never copy its events."
            ),
            "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "design_guide",
            "description": "The format of a check_design design, with a complete example. Read it before writing a design.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_design",
            "description": (
                "Check a new game's design (core loop, screen, state table, inputs, rules as data, win and lose, "
                "acceptance tests) and play its tests on the rules, without building anything. A refused design "
                "names the path to fix; fix it and call again with the whole design. The design that passes is "
                "the one new_project_from_spec builds and tests."
            ),
            "parameters": {
                "type": "object",
                "properties": {"design": {"type": "object", "description": "the design, as design_guide describes it"}},
                "required": ["design"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spec_guide",
            "description": "The format of a new_project_from_spec spec, with a complete small example. Read it before writing a spec.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "new_project_from_spec",
            "description": (
                "Make a new Construct 3 project from a spec (JSON: objects, layouts with layers and instances, "
                "sheets with events) that builds the design check_design passed, play the design's tests on it "
                "in the editor, and make it the person's project; it is sent as a .c3p after the reply. "
                "Read spec_guide first and look up every condition and action with lookup_ace. A refused spec "
                "built nothing: its lines name the spec path, or the design's test and step, to fix; fix those and "
                "call again with the whole spec."
            ),
            "parameters": {
                "type": "object",
                "properties": {"spec": {"type": "object", "description": "the spec, as spec_guide describes it"}},
                "required": ["spec"],
            },
        },
    },
]
# the design paragraphs of SPEC_GUIDE name check_design, which quick mode does not have
QUICK_GUIDE = re.sub(r"The spec builds the design check_design passed.*?(?=A board of crossings)", "", SPEC_GUIDE, flags=re.S)
QUICK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "new_project_from_spec",
            "description": (
                "Make a new Construct 3 project from a spec (JSON: objects, layouts with layers and instances, "
                "sheets with events), check it, and make it the person's project; it is sent as a .c3p after the "
                "reply. A refused spec built nothing: its lines name the spec paths to fix "
                "with patch_spec."
            ),
            "parameters": TOOLS[4]["function"]["parameters"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_spec",
            "description": (
                "Change the spec sent last at the paths a refusal named, and build it again; use it after a "
                "refusal instead of sending the whole spec. Each change sets a value, deletes, or inserts."
            ),
            "parameters": {
                "type": "object",
                "properties": {"changes": {"type": "array", "items": {"type": "object"}, "description": (
                    '[{"path": "spec.objects[0].size", "value": [2, 2]}, {"path": "spec.layouts[0].instances[1]", '
                    '"delete": true}, {"path": "spec.sheets[0].events[2]", "insert": {...}}]')}},
                "required": ["changes"],
            },
        },
    },
]
TEMPLATE_TOOL = {
    "type": "function",
    "function": {
        "name": "new_project_from_template",
        "description": (
            "Copy an official game template (an id starting with template- from search_examples) as the person's "
            "new project, renamed to name; it is sent as a .c3p after the reply. Only when a template is close to "
            "the game asked for; then change it with edit_sheet."
        ),
        "parameters": {
            "type": "object",
            "properties": {"template_id": {"type": "string"}, "name": {"type": "string"}},
            "required": ["template_id", "name"],
        },
    },
}
if TEMPLATE_COPY:
    TOOLS.append(TEMPLATE_TOOL)

PROMPT = """

To make a new game ("做个贪吃蛇", "做个五子棋"), or an example the person asks for as a file ("做一个例子",
"做个例子", "给我个工程", "发我 c3p", "来个 demo"), in this order; words alone do not answer such a request:
1. search_examples with the genre's words, then read_example on the closest one: how it is built, not its events.
2. design_guide, then check_design with the whole game as a design: the core loop, the state, the inputs, the
   rules, win and lose, the restart, and tests that play them. A small example of one mechanic ("做个小例子",
   a toggle, a countdown, a drag) is never won or lost: "win": "none" and "lose": "none", and no restart. Fix
   what a refusal names until it passes.
3. spec_guide, look up every condition and action with lookup_ace, then new_project_from_spec: one event per
   rule of the passed design. The build plays the design's tests in the editor; fix what a refusal names and
   call again.
Make the smallest version of the game that plays: one screen, two players sharing the device rather than a
computer opponent, no menus, levels or settings, unless the person asks for them; the art plain shapes. Once it
is built, it is the person's project and goes to them as a
file after your reply: say in plain words what the game does and how to play it, then that the file follows; it
opens in Construct 3 from Menu > Project > Open."""
PROMPT_NO_TEMPLATES = ""  # a hint to name an official example made the model name one that does not exist
PROMPT_TEMPLATES = """ When search_examples shows an official template (an id starting with template-) close to the
game asked for, new_project_from_template copies it instead, and edit_sheet adapts it; when none is close, say so
and build from a spec."""


QUICK_PROMPT = """

To make a new game or example ("做个贪吃蛇", "做一个小例子"): a quick prototype, made fast.
1. Write the smallest spec that shows the idea, as the spec format below says: one layout, one sheet, a few
   events. Look up with lookup_ace only a condition or action the format's example does not show.
2. new_project_from_spec with it. If it is refused, call patch_spec with a change for every line the refusal
   names; do not send the whole spec again. Lines starting "fixed" were already fixed for you.
Mistakes that cost a refusal each:
- Every name (object, layout, layer, sheet, variable) is English letters, digits and _; the player never sees it.
- Native plugins in the spec are Sprite, Text, Array, Dictionary, Touch, Mouse, Keyboard. Bar is a generator
  component, not a Construct plugin. It expands to NinePatch objects; control the fill with its real object
  actions such as Set width. Bar has no Set value, Set maximum or Set fill color actions. A button is a Sprite with
  a "label"; a Touch object is named Touch.
- A tap on an object is Touch "on-touched-object" with parameters {"object": "<name>", "type": "start"}.
- A global variable is {"eventType": "variable", ...} at the top of the sheet; change it with System
  "set-eventvar-value" or "add-to-eventvar", the value an expression string ("1").
- Every event with conditions and actions has "eventType": "block".
Preserve every explicit requirement, including thresholds, tick spacing and attachment behavior.
A health bar uses current/max health for its fill, character width for its full length, and internal
100-point boundaries for ticks. Below 25% is red; otherwise below 50% is yellow; otherwise green.
Do not replace a requested addon plugin with a project example without explaining the capability limit.
No extra menus, levels, opponents or settings; plain shapes. Once it is built, it goes to the person as a file after
your reply: say in plain words what it does and how to try it, then that the file follows; it opens in
Construct 3 from Menu > Project > Open.

The spec format:
"""


def prompt() -> str:
    if QUICK:
        return QUICK_PROMPT + QUICK_GUIDE
    return PROMPT + (PROMPT_TEMPLATES if TEMPLATE_COPY else PROMPT_NO_TEMPLATES)


def _mark_file(project: Path) -> Path:
    return MARKS / (hashlib.md5(str(project.resolve()).lower().encode()).hexdigest()[:16] + ".json")


def _unique_id(project: Path) -> str:
    try:
        return json.loads((project / "project.c3proj").read_text(encoding="utf-8-sig")).get("uniqueId") or ""
    except (OSError, json.JSONDecodeError):
        return ""


def _project_digest(project: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in project.rglob("*") if p.is_file() and ".tmp" not in p.relative_to(project).parts):
        digest.update(path.relative_to(project).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _mark(project: Path, origin: str, verified: bool = False) -> None:
    MARKS.mkdir(parents=True, exist_ok=True)
    _mark_file(project).write_text(json.dumps({"uniqueId": _unique_id(project), "origin": origin,
                                             "verified_digest": _project_digest(project) if verified else None}), encoding="utf-8")


def is_new(project: Path | None) -> bool:
    """Whether the bot made this project, and it is still the one in the folder."""
    if not project:
        return False
    try:
        mark = json.loads(_mark_file(project).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(mark.get("uniqueId")) and mark["uniqueId"] == _unique_id(project)


def runtime_verified(project: Path) -> bool:
    """Whether editor tests passed for these exact project files."""
    if not is_new(project):
        return False
    mark = json.loads(_mark_file(project).read_text(encoding="utf-8"))
    return bool(mark.get("verified_digest")) and mark["verified_digest"] == _project_digest(project)


def _settle(session: Path, origin: str, verified: bool = False) -> Path:
    """The new project is the session's: forget the edits of whatever was there and mark it."""
    edits.reset(session)
    _mark(session, origin, verified)
    return session


STRAY = re.compile(r'\}\s*,\s*(?="(?:conditions|actions|children)"\s*$)')


def mend(text: str, tries: int = 8) -> str:
    """The JSON text with a block opened where the model closed the comment above it and went on with the block's
    keys: {"eventType": "comment", ...}, "actions": [...] (2026-10-04). And a list closed one level too early, then
    more events: ..."actions": [...]}]}]}, {"eventType": "comment", ... reached an object where an event was meant
    (22 resends of one spec, 2026-10-04): the last ]} before it goes, and balance() closes the end. The build checks
    what the spec then says."""
    for _ in range(tries):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            before = text[:e.pos]
            m = STRAY.search(before.rstrip().rstrip(":").rstrip())
            early = re.search(r"\]\s*\}\s*,\s*$", before) if e.msg.startswith("Expecting property name") \
                and text[e.pos:e.pos + 1] == "{" else None
            if m:
                text = text[:m.end()] + '{"eventType": "block", ' + text[m.end():]
            elif early:
                text = balance(before[:early.start()] + before[early.start():].replace("]", "", 1).replace("}", "", 1)
                               + text[e.pos:])
            else:
                return text
    return text


def balance(text: str) -> str:
    """The JSON text with its brackets put in order: a closer that does not match the innermost open bracket first
    closes what is still open inside it, a closer with nothing to match is dropped, and what is open at the end is
    closed. A long call from the model leaves a list open and closes the object around it (2026-10-04); the spec
    built from the result is checked like any other."""
    out, stack, quoted, escaped = [], [], False, False
    pairs = {"}": "{", "]": "["}
    for ch in text:
        if quoted:
            out.append(ch)
            escaped = ch == "\\" and not escaped
            if ch == '"' and not escaped:
                quoted = False
            continue
        if ch == '"':
            quoted, escaped = True, False
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if pairs[ch] not in stack:
                continue
            while stack[-1] != pairs[ch]:
                out.append("}" if stack.pop() == "{" else "]")
            stack.pop()
        out.append(ch)
    out.extend("}" if c == "{" else "]" for c in reversed(stack))
    return "".join(out)


def gather(spec, rest: dict) -> object:
    """The spec with the keys the call sent beside it; those keys alone when the call has no spec."""
    if isinstance(spec, dict):
        return {**spec, **{k: v for k, v in rest.items() if k not in spec}}
    return rest if spec is None else spec


def unwrap(arguments, key: str = "spec") -> object:
    """The spec (or design) out of a call wrapped as {"arguments": "<the call as text>"}, or the text as it is."""
    try:
        inner = json.loads(mend(arguments)) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        return arguments
    return inner.get(key, inner) if isinstance(inner, dict) else inner


def read_example(example_id: str, rag: Path, locale: str, read_before: int = 0) -> str:
    """Print an official example's event sheets. Its data id names the folder, optionally with -js or -ts."""
    if read_before >= 2:
        # the model read one example after another, 39 times, and ran out of steps (2026-10-04)
        return ("not read: two examples are enough. Go on: design_guide, then check_design with the game's design")
    root = EXAMPLES / "example-projects"
    ok = re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", str(example_id))
    folder = next((root / f"{example_id}{s}" for s in ("", "-js", "-ts") if ok and (root / f"{example_id}{s}" / "project.c3proj").is_file()), None)
    if not folder:
        return (f"no example {example_id!r}; take an id that search_examples printed, before the colon, or go "
                f"on without one: design_guide, then check_design")
    proc = copilot.run_script("print_sheet", [], folder, locale=locale, limit=6000, timeout=60, rag=rag)
    if proc.returncode != 0:
        return f"example read failed: {(proc.stdout + proc.stderr).strip()}"
    text = "\n".join(l for l in (proc.stdout + proc.stderr).strip().splitlines()
                     if not re.search(r"lines not printed|print_sheet\.py .*--events|--limit 0", l))
    return (text[:6500] + "\n-- that is enough to see how it is built: which object holds what, which trigger does "
            "what. Name it in the design's \"reference\" with what you take, and write your own events. Next: "
            "design_guide, then check_design")


def design_guide(rag: Path) -> str:
    """The installed design reference, starting at its format."""
    text = (copilot.get_runtime().skills_root / "skills" / "construct3-agent-plugin" / "references" / "designing-a-game.md").read_text(encoding="utf-8")
    return text[text.index("## The design"):]


def _design_file(session: Path) -> Path:
    return MARKS / (_mark_file(session).stem + ".design.json")


NOTHING_LATER = "nothing left out"  # the one item of a design's "later" that builds the whole request (game_model.py)


def left_for_later(session: Path) -> list[str]:
    """What the design kept for session leaves out of the request. check_design asks the model to name these when
    it reports; a reply to "还原一模一样的效果图" built a stand-in for the picture and did not say so (2026-10-18)."""
    try:
        later = json.loads(_design_file(session).read_text(encoding="utf-8")).get("later")
    except (OSError, ValueError, AttributeError):
        return []
    if not isinstance(later, list):
        return []
    return [v.strip() for v in later if isinstance(v, str) and v.strip() and v.strip() != NOTHING_LATER]


# The last refusal of each kind per session: a model sent one refused design 32 times unchanged (2026-10-04)
_refused: dict[tuple[str, str], tuple[str, str]] = {}


_last_spec: dict[str, object] = {}  # session -> the spec sent last, which patch_spec changes


def _key(payload) -> str:
    return hashlib.md5(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _again(kind: str, session: Path, payload) -> str | None:
    """The answer to a payload sent again unchanged after a refusal, or None."""
    last = _refused.get((kind, str(session)))
    if last and last[0] == _key(payload):
        return (f"refused again: this {kind} is the one refused just before, unchanged, so it fails the same way. "
                f"Change what the first line below names, or find another way to do it, then send it again:\n"
                + "\n".join(last[1].splitlines()[:6]))
    return None


def _refuse(kind: str, session: Path, payload, text: str) -> str:
    _refused[(kind, str(session))] = (_key(payload), text)
    return text


def check_design(design, session: Path, rag: Path, read_one: bool) -> str:
    """Check the design through Copilot and keep it for the build when it passes."""
    if isinstance(design, str):
        try:
            design = json.loads(design)
        except json.JSONDecodeError as e:
            return f"refused: the design is not valid JSON, {e.msg} at character {e.pos}"
    if not read_one:
        return ("refused: read the closest official example first: search_examples with the genre's words, then "
                "read_example with the id of the closest one, then check_design again")
    again = _again("design", session, design)
    if again:
        return again
    MARKS.mkdir(parents=True, exist_ok=True)
    with copilot.temporary_directory() as tmp:
        path = Path(tmp) / "design.json"
        path.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
        proc = copilot.run_script("check_design", [str(path)], limit=6000, timeout=60, rag=rag)
        out = (proc.stdout + proc.stderr).strip()
        if proc.returncode == 0:
            shutil.copyfile(path, _design_file(session))
            return (re.sub(r" Next, build the game.*", "", out) + "\n-- the design passed and is kept. Next: spec_guide, "
                    "look up each condition and action with lookup_ace, then new_project_from_spec, one event per "
                    "rule; the build plays these tests in the editor")
    return _refuse("design", session, design,
                   out + "\n-- refused; fix the design at the paths above and call check_design again with the whole design")


def play_tests(project: Path, rag: Path, design: Path | None = None) -> str:
    """Play the kept design's tests on the built project in the headless editor; return why it fails, or ""."""
    if not EDITOR_CHECK:
        return ""
    with _editor, copilot.temporary_directory() as tmp:
        try:
            proc = copilot.run_script("play_design", [str(design or _design_file(project)), "--profile", str(PROFILE),
                                     "--adopt-starts", "--out", str(Path(tmp) / "result.json")], project,
                                     limit=5000, timeout=PLAY_TIMEOUT, rag=rag)
        except subprocess.TimeoutExpired:
            return f"refused: editor verification timed out after {PLAY_TIMEOUT} s; nothing was sent"
    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0:
        return ""
    lines = [l for l in out.splitlines() if not l.startswith(("opened", "ran in", "next:", "  played"))]
    return ("refused, nothing was sent: editor verification did not complete successfully:\n"
            + "\n".join(lines)[:2500]
            + "\n-- resolve the reported failure and retry verification. If a failed test names a rule or event, "
              "compare that event with the design. An unavailable or timed-out editor is not a failed gameplay assertion.")


def from_spec(spec, session: Path, rag: Path, locale: str) -> tuple[Path | None, str]:
    """Build spec into the session folder; return the project, or None and the refusal."""
    if not QUICK and not _design_file(session).is_file():
        return None, ("refused, nothing was built: no checked design. Call design_guide, then check_design with the "
                      "game's design until it passes, then this with the spec that builds it")
    if isinstance(spec, str):
        try:
            spec = json.loads(mend(spec))
        except json.JSONDecodeError as e:
            return None, (f"refused, nothing was built:\nspec: not valid JSON, {e.msg} at character {e.pos}, here: "
                          f"{spec[max(0, e.pos - 120):e.pos]}<<HERE>>{spec[e.pos:e.pos + 60]}")
    notes: list[str] = []
    if QUICK:
        # the refusal's paths are those of the fixed spec, so patch_spec starts from it
        spec, notes = quick_fix.tidy(spec)
    _last_spec[str(session)] = spec
    again = _again("spec", session, spec)
    if again:
        return None, again
    text = json.dumps(spec, ensure_ascii=False)
    if len(text) > SPEC_MAX:
        return None, f"refused, nothing was built:\nspec: {len(text)} characters, more than {SPEC_MAX}; make the game smaller"
    with copilot.temporary_directory() as tmp:
        path = Path(tmp) / "spec.json"
        candidate = Path(tmp) / "project"
        path.write_text(text, encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, str(HERE / "spec_build.py"), str(path), "--out", str(candidate),
                                   "--rag", str(rag), "--locale", locale],
                                  capture_output=True, text=True, encoding="utf-8", timeout=BUILD_TIMEOUT,
                                  env=copilot.child_environment())
        except subprocess.TimeoutExpired:
            return None, f"refused, nothing was built: the build ran past {BUILD_TIMEOUT} s; make the game smaller"
        out = "\n".join([*(f"fixed: {line}" for line in notes), (proc.stdout + proc.stderr).strip()])
        if proc.returncode != 0:
            if proc.returncode != 1:
                log.warning("spec_build exit %s: %s", proc.returncode, out[-500:])
            return None, _refuse("spec", session, spec, out)
        refused = "" if QUICK else play_tests(candidate, rag, _design_file(session))
        if refused:
            return None, _refuse("spec", session, spec, refused)
        if session.exists():
            shutil.rmtree(session)
        shutil.copytree(candidate, session)
        out = out.replace(str(candidate), str(session))
    verified = not QUICK and EDITOR_CHECK
    evidence = "editor tests passed" if verified else "structural check passed; editor runtime is unverified"
    return _settle(session, "spec", verified), out + (
        f"\n-- built; {evidence}. It is the person's project and goes to them as a file after your reply. In the "
        "reply say in plain words what the game is and how to play it, then that the file follows")


PATH_STEP = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_-]*)|\.?\[(\d+)\]|\.(\d+)")


def _steps(path: str) -> list:
    """'spec.objects[0].size' -> ['objects', 0, 'size']."""
    path = re.sub(r"^spec\.?", "", path.strip())
    steps, pos = [], 0
    for m in PATH_STEP.finditer(path):
        if m.start() != pos:
            raise ValueError(f"{path!r} is not a path like spec.objects[0].size")
        steps.append(m.group(1) if m.group(1) is not None else int(m.group(2) or m.group(3)))
        pos = m.end()
    if pos != len(path) or not steps:
        raise ValueError(f"{path!r} is not a path like spec.objects[0].size")
    return steps


def patch_spec(changes, session: Path, rag: Path, locale: str) -> tuple[Path | None, str]:
    """Apply changes to the spec sent last and build it, so a refusal costs a few lines instead of the whole spec."""
    spec = _last_spec.get(str(session))
    if spec is None:
        return None, "refused: no spec was sent yet; call new_project_from_spec with the whole spec first"
    spec = json.loads(json.dumps(spec))
    if isinstance(changes, dict):
        changes = [changes]
    for change in changes if isinstance(changes, list) else []:
        try:
            steps = _steps(str(change.get("path", "")))
            parent = spec
            for step in steps[:-1]:
                parent = parent[step]
            last = steps[-1]
            if change.get("delete"):
                del parent[last]
            elif "insert" in change and isinstance(parent, list):
                parent.insert(last, change["insert"])
            elif isinstance(parent, list) and last == len(parent):
                parent.append(change.get("value"))
            else:
                parent[last] = change.get("value")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            return None, (f"refused, nothing was built: change {change!r} does not apply: {e}. A change is "
                          '{"path": "spec.objects[0].size", "value": [2, 2]}, {"path": ..., "delete": true} or '
                          '{"path": "spec.sheets[0].events[1]", "insert": {...}}')
    return from_spec(spec, session, rag, locale)


def from_template(template_id: str, name: str, session: Path, rag: Path, locale: str) -> tuple[Path | None, str]:
    """Copy an official template into the session folder under a new name and uniqueId, then check it."""
    root = EXAMPLES / "example-projects"
    if not re.fullmatch(r"template-[a-z0-9-]+", template_id or "") or not (root / template_id / "project.c3proj").is_file():
        ids = sorted(p.name for p in root.glob("template-*") if (p / "project.c3proj").is_file())
        return None, f"no template {template_id!r}; the templates are {', '.join(ids)}"
    name = " ".join(str(name).split())[:40] or template_id
    with copilot.temporary_directory() as tmp:
        candidate = Path(tmp) / "project"
        shutil.copytree(root / template_id, candidate, ignore=shutil.ignore_patterns(".git", ".tmp", "*.uistate.json"))
        c3proj = candidate / "project.c3proj"
        data = json.loads(c3proj.read_text(encoding="utf-8-sig"))
        data["name"] = name
        data["uniqueId"] = "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
        with c3proj.open("w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, indent="\t", ensure_ascii=False))
        proc = copilot.run_script("check_project", [], candidate, locale=locale, timeout=90, rag=rag)
        checked = re.sub(r"; next, review the design.*", "", (proc.stdout + proc.stderr).strip())
        if proc.returncode != 0:
            return None, f"refused: copied template failed its structural check\n{checked}"
        if session.exists():
            shutil.rmtree(session)
        shutil.copytree(candidate, session)
    return _settle(session, f"template {template_id}"), f"copied {template_id} as {name!r}\n{checked}\n-- editor runtime is unverified"


def pack(project: Path, rag: Path) -> Path:
    """The project as sessions/_new/out/<hash>/<name>.c3p, packed through Copilot."""
    out = MARKS / "out" / _mark_file(project).stem
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    target = out / f"{edits.project_name(project)}.c3p"
    proc = copilot.run_script("pack_project", ["--out", str(target)], project, timeout=120, rag=rag)
    if proc.returncode != 0 or not target.is_file():
        raise RuntimeError(f"pack_project.py exit {proc.returncode}: {(proc.stdout + proc.stderr).strip()[-500:]}")
    return target
