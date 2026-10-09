"""Mechanical fixes to a spec before spec_build.py checks it, for quick prototypes (C3BOT_QUICK=1).

Each fix is one a refusal would have asked the model for and that has a single right answer, so the model is not
sent round again to write the whole spec for it. A fix that would change what the game does is left to the refusal.
"""
from __future__ import annotations

import json
import re

NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}$")
SHEET_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_ ]{0,31}$")
KEYS = {
    "spec": {"name", "viewport", "theme", "palette", "primary", "objects", "layouts", "sheets"},
    "object": {"name", "plugin", "shape", "size", "frames", "outline", "outline_color", "shadow", "behaviors", "variables"},
    "layout": {"name", "sheet", "size", "screen", "layers", "instances", "backdrop"},
    "layer": {"name", "color", "parallax"},
    "instance": {"object", "layer", "col", "row", "repeat", "gap", "index", "variables", "frame", "visible", "text", "anchor",
                 "longest", "width", "height", "size", "color", "on", "align", "dx", "dy", "below", "above", "over",
                 "label", "band"},
}
PLUGINS = ("Sprite", "Text", "Bar", "Array", "Dictionary", "Touch", "Mouse", "Keyboard")
SINGLE = ("Touch", "Mouse", "Keyboard")
# plugin names a model writes for one of PLUGINS
PLUGIN_ALIASES = {"button": "Sprite", "ui-button": "Sprite", "shape": "Sprite", "tiledbackground": "Sprite",
                  "textobject": "Text", "label": "Text", "text object": "Text", "精灵": "Sprite", "文本": "Text",
                  "文字": "Text", "按钮": "Sprite", "触摸": "Touch", "鼠标": "Mouse", "键盘": "Keyboard", "数组": "Array"}
BANDS = ("title", "status", "stage", "hint")
EVENT_KEYS = {"conditions", "actions", "children"}


def tidy(spec: dict) -> tuple[dict, list[str]]:
    """Return the spec with its mechanical mistakes fixed, and one line per fix for the model to read."""
    notes: list[str] = []
    if not isinstance(spec, dict):
        return spec, notes
    _top(spec, notes)
    renames = _names(spec, notes)
    if renames:
        spec = _rename(spec, renames)
    _objects(spec, notes)
    _layouts(spec, notes)
    _declare_inputs(spec, notes)
    _sheets(spec, notes)
    return spec, notes


def _top(spec: dict, notes: list[str]) -> None:
    name = spec.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 40:
        spec["name"] = (name if isinstance(name, str) and name else "Prototype")[:40]
        notes.append(f"spec.name: set to {spec['name']!r}")
    for key in sorted(set(spec) - KEYS["spec"]):
        value = spec.pop(key)
        layouts = spec.get("layouts")
        if key in ("layers", "instances") and isinstance(layouts, list) and layouts and isinstance(layouts[0], dict) \
                and key not in layouts[0]:
            layouts[0][key] = value
            notes.append(f"spec.{key}: moved to spec.layouts[0]")
        else:
            notes.append(f"spec.{key}: dropped, a spec has no such key")


def _safe(name: str, used: set[str], prefix: str, pattern: re.Pattern) -> str:
    ascii_part = re.sub(r"[^A-Za-z0-9_]", "", name)
    base = ascii_part if ascii_part and ascii_part[0].isalpha() and pattern.match(ascii_part) else prefix
    out, n = base, 1
    while out in used:
        n += 1
        out = f"{base}{n}"
    used.add(out)
    return out


def _names(spec: dict, notes: list[str]) -> dict[str, str]:
    """Invalid names of objects, layouts, layers, sheets and global variables -> valid ones."""
    renames: dict[str, str] = {}
    used: set[str] = set()
    items = []
    for i, o in enumerate(spec.get("objects") or []):
        if isinstance(o, dict):
            items.append((o, "name", f"spec.objects[{i}]", "Obj", NAME))
    for i, lay in enumerate(spec.get("layouts") or []):
        if isinstance(lay, dict):
            items.append((lay, "name", f"spec.layouts[{i}]", "Layout", SHEET_NAME))
            for j, layer in enumerate(lay.get("layers") or []):
                if isinstance(layer, dict):
                    items.append((layer, "name", f"spec.layouts[{i}].layers[{j}]", "Layer", SHEET_NAME))
    for i, sh in enumerate(spec.get("sheets") or []):
        if isinstance(sh, dict):
            items.append((sh, "name", f"spec.sheets[{i}]", "Sheet", SHEET_NAME))
            for j, ev in enumerate(sh.get("events") or []):
                if isinstance(ev, dict) and ev.get("eventType") == "variable":
                    items.append((ev, "name", f"spec.sheets[{i}].events[{j}]", "var", NAME))
    for item, key, _, _, pattern in items:
        if isinstance(item.get(key), str) and pattern.match(item[key]):
            used.add(item[key])
    for item, key, where, prefix, pattern in items:
        old = item.get(key)
        if isinstance(old, str) and pattern.match(old):
            continue
        if isinstance(old, str) and old in renames:
            item[key] = renames[old]
            continue
        new = _safe(old if isinstance(old, str) else "", used, prefix, pattern)
        if isinstance(old, str) and old:
            renames[old] = new
        item[key] = new
        notes.append(f"{where}.name: {old!r} -> {new!r} (names are English; the player never sees them)")
    return renames


def _rename(spec: dict, renames: dict[str, str]) -> dict:
    """Every string that is an old name, or holds one inside an expression, gets the new one."""
    longest = sorted(renames, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(n) for n in longest))

    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str):
            if value in renames:
                return renames[value]
            # inside an expression, but not inside a quoted string the player reads
            parts = re.split(r'("(?:[^"\\]|\\.)*")', value)
            return "".join(p if p.startswith('"') else pattern.sub(lambda m: renames[m.group(0)], p) for p in parts)
        return value

    return walk(spec)


def _whole(value, lo: int, hi: int):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return min(hi, max(lo, round(value)))


def _objects(spec: dict, notes: list[str]) -> None:
    for i, o in enumerate(spec.get("objects") or []):
        if not isinstance(o, dict):
            continue
        where = f"spec.objects[{i}]"
        plugin = o.get("plugin")
        if plugin not in PLUGINS:
            new = PLUGIN_ALIASES.get(str(plugin).lower()) or next((p for p in PLUGINS if p.lower() == str(plugin).lower()), None) \
                or ("Text" if "text" in str(plugin).lower() else "Sprite")
            o["plugin"] = new
            notes.append(f"{where}.plugin: {plugin!r} -> {new!r}")
        if o["plugin"] in SINGLE and o.get("name") != o["plugin"]:
            notes.append(f"{where}.name: {o.get('name')!r} -> {o['plugin']!r}, the one name it has")
            o["name"] = o["plugin"]
        drop = set(o) - KEYS["object"]
        if o["plugin"] == "Text":
            drop |= set(o) & {"frames", "shape", "size", "outline", "outline_color", "shadow"}
        for key in sorted(drop):
            o.pop(key)
            notes.append(f"{where}.{key}: dropped, a {o['plugin']} object has no such key")
        size = o.get("size")
        if isinstance(size, list) and len(size) == 2:
            fixed = [_whole(v, 1, 16) for v in size]
            if None not in fixed and fixed != size:
                o["size"] = fixed
                notes.append(f"{where}.size: {size} -> {fixed}, whole grid units from 1 to 16")


def _layouts(spec: dict, notes: list[str]) -> None:
    sheets = [s.get("name") for s in spec.get("sheets") or [] if isinstance(s, dict)]
    for i, lay in enumerate(spec.get("layouts") or []):
        if not isinstance(lay, dict):
            continue
        where = f"spec.layouts[{i}]"
        for key in sorted(set(lay) - KEYS["layout"]):
            lay.pop(key)
            notes.append(f"{where}.{key}: dropped, a layout has no such key")
        if sheets and lay.get("sheet") not in sheets:
            notes.append(f"{where}.sheet: {lay.get('sheet')!r} -> {sheets[0]!r}")
            lay["sheet"] = sheets[0]
        layers = [ly for ly in lay.get("layers") or [] if isinstance(ly, dict)]
        for j, layer in enumerate(layers):
            for key in sorted(set(layer) - KEYS["layer"]):
                layer.pop(key)
                notes.append(f"{where}.layers[{j}].{key}: dropped, a layer has only name, color, parallax")
        names = [ly.get("name") for ly in layers]
        for j, inst in enumerate(lay.get("instances") or []):
            if not isinstance(inst, dict):
                continue
            iw = f"{where}.instances[{j}]"
            if "object" not in inst:
                for alt in ("type", "name", "objectClass"):
                    if isinstance(inst.get(alt), str):
                        inst["object"] = inst.pop(alt)
                        notes.append(f"{iw}.{alt}: written as \"object\"")
                        break
            for key in ("row", "col"):
                v = inst.get(key)
                if isinstance(v, str) and v != "center":
                    inst.pop(key)
                    if v in BANDS and "band" not in inst:
                        inst["band"] = v
                        notes.append(f"{iw}.{key}: {v!r} written as \"band\": {v!r}")
                    else:
                        notes.append(f"{iw}.{key}: {v!r} dropped, a whole number or \"center\"")
                elif isinstance(v, float):
                    inst[key] = round(v)
            for key in sorted(set(inst) - KEYS["instance"]):
                inst.pop(key)
                notes.append(f"{iw}.{key}: dropped, an instance has no such key")
            if names and inst.get("layer") not in names:
                notes.append(f"{iw}.layer: {inst.get('layer')!r} -> {names[-1]!r}")
                inst["layer"] = names[-1]


def _event(ev: dict, where: str, notes: list[str]) -> None:
    if not ev.get("eventType") and EVENT_KEYS & set(ev):
        ev["eventType"] = "block"
        notes.append(f"{where}.eventType: set to \"block\"")
    for key in ("conditions", "actions"):
        for k, ace in enumerate(ev.get(key) or []):
            if isinstance(ace, dict) and "objectClass" not in ace and isinstance(ace.get("object"), str) \
                    and "parameters" in ace:
                ace["objectClass"] = ace.pop("object")
                notes.append(f"{where}.{key}[{k}].object: written as \"objectClass\"")
    for k, child in enumerate(ev.get("children") or []):
        if isinstance(child, dict):
            _event(child, f"{where}.children[{k}]", notes)


def _sheets(spec: dict, notes: list[str]) -> None:
    for i, sh in enumerate(spec.get("sheets") or []):
        if not isinstance(sh, dict) or not isinstance(sh.get("events"), list):
            continue
        out = []
        for j, ev in enumerate(sh["events"]):
            if not isinstance(ev, dict):
                out.append(ev)
                continue
            where = f"spec.sheets[{i}].events[{j}]"
            text = ev.pop("comment", None) or ev.pop("comments", None)
            _event(ev, where, notes)
            if ev.get("eventType") in ("block", "group") and not (out and isinstance(out[-1], dict)
                                                                 and out[-1].get("eventType") == "comment"):
                out.append({"eventType": "comment", "text": text if isinstance(text, str) and text
                            else _describe(ev)})
                notes.append(f"{where}: a comment added above it")
            out.append(ev)
        sh["events"] = out


TRIGGER_WORDS = {"on-touched-object": "{object} is tapped", "on-tap-object": "{object} is tapped",
                 "on-object-clicked": "{object} is clicked", "on-start-of-layout": "the layout starts",
                 "every-x-seconds": "a timer ticks", "every-tick": None, "on-key-pressed": "a key is pressed",
                 "on-any-touch-start": "the screen is tapped", "on-collision-with-another-object": "{objectClass} hits {object}"}
ACTION_WORDS = {"add-to-eventvar": "add to {variable}", "subtract-from-eventvar": "take from {variable}",
                "set-eventvar-value": "set {variable}", "toggle-boolean-eventvar": "switch {variable}",
                "set-text": "show it on {objectClass}", "destroy": "remove {objectClass}",
                "create-object": "create {object-to-create}", "spawn-another-object": "spawn {object}",
                "set-animation-frame": "change {objectClass}'s look", "set-visible": "show or hide {objectClass}",
                "restart-layout": "restart"}


def _words(table: dict, ace: dict) -> str:
    params = {k: v for k, v in (ace.get("parameters") or {}).items() if isinstance(v, str)}
    template = table.get(ace.get("id", ""))
    if template is None:
        return f"{str(ace.get('id', '')).replace('-', ' ')} {ace.get('objectClass', '')}".strip()
    try:
        return template.format_map({"objectClass": ace.get("objectClass", ""), **params})
    except KeyError:
        return template.split(" {")[0]


def _describe(ev: dict) -> str:
    """A one-sentence comment from what the event does, for an event the model left without one."""
    conds = [_words(TRIGGER_WORDS, c) for c in ev.get("conditions") or []
             if isinstance(c, dict) and c.get("id") != "every-tick"][:1]
    acts = list(dict.fromkeys(_words(ACTION_WORDS, a) for a in ev.get("actions") or [] if isinstance(a, dict)))
    what = ", ".join(acts[:3]) or "nothing yet"
    return f"When {conds[0]}: {what}" if conds else f"Every tick: {what}"


def _declare_inputs(spec: dict, notes: list[str]) -> None:
    """Touch, Mouse and Keyboard that the events use get their object; a lone Text or Sprite stands for its plugin."""
    objects = [o for o in spec.get("objects") or [] if isinstance(o, dict)]
    declared = {o.get("name") for o in objects}
    used = set(re.findall(r'"objectClass":\s*"([^"]+)"', json.dumps(spec.get("sheets") or [], ensure_ascii=False)))
    for single in SINGLE:
        if single in used and single not in declared:
            spec.setdefault("objects", []).append({"name": single, "plugin": single})
            notes.append(f"spec.objects: {single} added, the events use it")
    for plugin in ("Text", "Sprite"):
        if plugin in used and plugin not in declared:
            of = [o["name"] for o in objects if o.get("plugin") == plugin]
            if len(of) == 1:
                spec["sheets"] = json.loads(re.sub(rf'("objectClass":\s*"){plugin}"', rf'\g<1>{of[0]}"',
                                                   json.dumps(spec["sheets"], ensure_ascii=False)))
                notes.append(f"spec.sheets: objectClass {plugin!r} -> {of[0]!r}, the one {plugin} object")
