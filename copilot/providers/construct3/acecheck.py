"""The ACE check: every condition, action and expression a reply names must be one lookup_ace prints, in the
schema locale or in English, so the person finds it in the editor by that name."""
from __future__ import annotations

import difflib
import re
import uuid
from pathlib import Path

from .tools import PROJECT_READERS, run_script

LIST_ACES = (
    "List every event-sheet condition, action or expression your last answer names. Leave out scripting API "
    "methods and properties (anything called from JavaScript, e.g. isMouseButtonDown, getAllInstances). "
    "Reply with JSON only: "
    '{"aces": [{"object": "SnakeHead", "plugin": "Sprite", "name": "设置位置", "written_as": "action"}, '
    '{"object": "Player", "plugin": "8Direction", "name": "设置最大速度", "written_as": "action"}]}. object is the '
    "object as the answer writes it (System, an object name or a behavior); plugin is the plugin or behavior "
    "that has the ACE, as lookup_ace takes it (System, Sprite, Text, 8Direction), never an object name; name is "
    "the display name alone, without parameters or the object; written_as is how the answer uses it: condition "
    "(before the arrow), action (after the arrow) or expression (inside a parameter). "
    'An answer that names none gives {"aces": []}.'
)
KINDS = ("condition", "action", "expression")
# the request_id prefix of the check's own lookups in the task store, which tells them from the model's calls
CHECK_REQUEST = "acecheck:"
NOT_AN_OBJECT = "is not an object of this project"


def _lookup(args: list[str], project: Path | None, **options) -> str:
    return run_script("lookup_ace", args, project, request_id=CHECK_REQUEST + uuid.uuid4().hex, **options)


def _norm(s: str) -> str:
    return re.sub(r"[\s\"'“”‘’：:]", "", s).lower()


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
    """Return 'object: name' for each named ACE that the full lookup of its plugin does not print, and one line
    for a plugin that does not resolve, whose names are then not looked up.

    An entry is looked up by its plugin, or by its object when it gives none: the object is often a name of the
    model's own design (SnakeHead), which the project does not hold (2026-10-16: 94 failed lookups in one
    conversation, and since the check named only the ACEs, the model renamed them and kept the object).

    seen is project_text(): a name the project's printed events or scripts hold is not checked, because a
    summary of a sent project names its variables, its addons' ACEs and actions with their parameters, which
    the schema lookup does not print (2026-10-04: fifty such names used up every step)."""
    cache: dict[str, dict[str, str]] = {}
    raw: dict[str, str] = {}  # the full lookups, for the closest names of a miss
    unknown: set[str] = set()  # the plugins whose lookup says they are none, reported once
    missing = []
    for ace in aces:
        shown, name = str(ace.get("object") or ""), str(ace.get("name", ""))
        obj = str(ace.get("plugin") or "") or shown
        written = str(ace.get("written_as", ""))
        if not obj or not name:
            continue
        if seen and _norm(name) in seen:
            continue
        if obj in unknown:
            continue
        if shown and shown != obj:
            shown = f"{shown} ({obj})"
        else:
            shown = obj
        common = obj.lower() != "system"
        if obj not in cache:
            # the model may name an ACE in English as well as in the schema locale
            raw[obj] = _lookup([obj], project, limit=0) + "\n" + _lookup([obj], project, limit=0, locale="en-US")
            cache[obj] = _ace_lines(raw[obj], common)
            if NOT_AN_OBJECT in raw[obj]:
                unknown.add(obj)
                missing.append(f"{obj} is not a plugin or behavior, so its ACE names could not be checked; name the "
                               "plugin or behavior that has them (e.g. Sprite, Text, 8Direction)")
                continue
        found = cache[obj]
        if not any(_norm(name) in found[k] for k in KINDS):
            # a bare lookup leaves out the ACEs every world object shares (_common), so retry with the name as a word
            found = _join(found, _ace_lines(_lookup([obj, name], project), common),
                          _ace_lines(_lookup([obj, name], project, locale="en-US"), common))
        kinds = [k for k in KINDS if _norm(name) in found[k]]
        if not kinds:
            near = _near(raw[obj], name)
            missing.append(f"{shown}: {name}" + ("" if common else " (System has no such ACE; if every object has it, "
                                                                 "it belongs to the object itself, so name the object)")
                           + (f"; closest real names: {', '.join(near)}" if near else ""))
        elif written in KINDS and written not in kinds:
            # 2026-10-04: Pick top/bottom, a condition, was written after the arrow as if it were an action
            missing.append(f"{shown}: {name} is a {' or '.join(kinds)}, but the answer writes it as {'an' if written[0] in 'ae' else 'a'} {written}; "
                           "a condition goes before the arrow, an action after it")
    return missing
