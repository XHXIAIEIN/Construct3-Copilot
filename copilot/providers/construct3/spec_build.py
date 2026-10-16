"""Build a Construct 3 folder project from a JSON spec, with the installed Agent-Skills generator helpers.

    python spec_build.py SPEC.json --out FOLDER [--rag RAG] [--locale zh-CN]

The spec is data a chat model wrote; this file is the only code that runs. It checks the spec,
draws the placeholder images and writes the object types, layouts and project.c3proj through
skills/construct3-agent-plugin/assets/build_project.py, starting from the RAG's empty project
(data/c3-new-project), then puts each sheet's events in with edit_sheet.py, one operation per
top-level event, and runs check_project.py. Every refusal names the spec path to change and what
to write there. The project is built in a scratch folder and moved to --out only when the
checker passes, so a refused spec leaves --out as it was.

exit codes: 0 built and checked; 1 refused, nothing written; 2 required tooling or data is missing
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import re
import shutil
import string
import sys
from pathlib import Path

DEFAULT_RAG = Path(os.environ.get("COPILOT_RAG") or Path(__file__).resolve().parents[3].parent / "Construct3-RAG")
SPEC_MAX = 60_000          # characters of spec JSON
OBJECTS_MAX = 40
LAYOUTS_MAX = 4
INSTANCES_MAX = 1500       # after repeat
EVENTS_MAX = 400           # every event, condition and action counted once
SIZE_MAX = 16              # units on a side of one sprite
STEP_TIMEOUT = 60          # seconds for one edit_sheet.py or check_project.py run

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from copilot.providers.construct3 import quick_fix  # noqa: E402
from copilot.providers.construct3 import services as copilot  # noqa: E402

NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}$")
SHEET_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_ ]{0,31}$")
SHAPES = ("rect", "circle", "triangle", "grid")
WORLD = ("Sprite", "Text")
NONWORLD = {"Array": "Arr", "Dictionary": "Dictionary"}
SINGLE = {"Touch": {"use-mouse-input": True}, "Mouse": {}, "Keyboard": {}}
PLUGINS = (*WORLD, "Bar", *NONWORLD, *SINGLE)
# behavior name on the object -> (behavior id, the template constant with its instance properties)
BEHAVIORS = {"Tween": ("Tween", "TWEEN"), "Timer": ("Timer", "TIMER"), "Solid": ("solid", "SOLID"),
             "Sine": ("Sin", "SINE"), "Bullet": ("Bullet", "BULLET"), "8Direction": ("EightDir", "EIGHT_DIR"),
             "Platform": ("Platform", "PLATFORM"), "MoveTo": ("MoveTo", "MOVE_TO"), "Rotate": ("Rotate", "ROTATE"),
             "DragDrop": ("DragnDrop", "DRAG_DROP"), "ScrollTo": ("scrollto", "SCROLL_TO"),
             "DestroyOutsideLayout": ("destroy", "DESTROY_OUTSIDE"), "BoundToLayout": ("bound", "BOUND_TO_LAYOUT")}
KEYS = {
    "spec": {"name", "viewport", "theme", "palette", "primary", "objects", "layouts", "sheets"},
    "object": {"name", "plugin", "shape", "size", "frames", "outline", "outline_color", "shadow", "behaviors", "variables"},
    "behavior": {"name", "properties"},
    "layout": {"name", "sheet", "size", "screen", "layers", "instances", "backdrop"},
    "layer": {"name", "color", "parallax"},
    "instance": {"object", "layer", "col", "row", "repeat", "gap", "index", "variables", "frame", "visible", "text", "anchor",
                 "longest", "width", "height", "size", "color", "on", "align", "dx", "dy", "below", "above", "over",
                 "label", "band"},
    "sheet": {"name", "events"},
}
# Themes: a mood in words, the colour of each role of the template's PALETTE, and the roles of the outline and the
# shadow when they are not ink. Each keeps the template's ratios: the backdrop's two colours at most 1.2:1, solid
# 3:1 on the backdrop, text in ink and dim readable on it, and solid, reward and danger 3:1 against the outline.
THEMES = {
    "greybox": ("grey blockout, the default", {}, {}),
    "day": ("light and clear: a pale blue backdrop, blue shapes, dark text",
            {"canvas": (240, 245, 250), "canvas_alt": (226, 236, 246), "solid": (64, 124, 196), "dim": (76, 88, 108),
             "ink": (26, 34, 50), "reward": (255, 190, 40), "danger": (232, 76, 64), "flash": (255, 255, 255)}, {}),
    "night": ("dark: a navy backdrop, bright shapes, light text",
              {"canvas": (22, 26, 42), "canvas_alt": (30, 35, 56), "solid": (92, 136, 230), "dim": (150, 162, 196),
               "ink": (238, 242, 250), "reward": (255, 200, 50), "danger": (244, 92, 80), "flash": (255, 255, 255),
               "shade": (8, 10, 18)}, {"outline_role": "shade", "shadow_role": "shade"}),
    "candy": ("warm and soft: a pink backdrop, raspberry shapes",
              {"canvas": (255, 241, 246), "canvas_alt": (250, 229, 238), "solid": (208, 66, 124), "dim": (112, 68, 100),
               "ink": (58, 28, 58), "reward": (255, 196, 56), "danger": (236, 72, 56), "flash": (255, 255, 255)}, {}),
}
# a green for what is on, right or done, which the template's palette leaves out; 3:1 against each theme's outline
GOOD = {"greybox": (64, 170, 90), "day": (52, 168, 96), "night": (90, 210, 120), "candy": (60, 170, 110)}
# a neutral grey for what is off or idle, which a theme's solid is not: day's solid is blue
GREY = {"greybox": (150, 150, 150), "day": (150, 156, 166), "night": (120, 126, 140), "candy": (160, 150, 156)}
# the conditions that name the object a finger touches, so that object is at least TOUCH
TAP_CONDITIONS = ("on-touched-object", "on-tap-object", "is-touching-object", "on-double-tap-object", "on-hold-object",
                  "on-object-clicked", "is-over-object")
# a stage screen puts a text held to an edge into the band on that edge
ANCHOR_BANDS = {"top-left": ("status", "left"), "top": ("status", "center"), "top-right": ("status", "right"),
                "left": ("stage", "left"), "center": ("stage", "center"), "right": ("stage", "right"),
                "bottom-left": ("hint", "left"), "bottom": ("hint", "center"), "bottom-right": ("hint", "right")}


def band_on_edge(band) -> tuple[str, str] | None:
    """(band, side) for an edge written where a band goes, "bottom" or "top-left"; None for anything else."""
    edge = {"middle": "center", "top-center": "top", "bottom-center": "bottom"}.get(band, band)
    return ANCHOR_BANDS.get(edge) if isinstance(edge, str) else None


EXAMPLE = ('{"name": "Gomoku", "objects": [{"name": "Cell", "plugin": "Sprite", "shape": "rect", "size": [1, 1], '
           '"frames": ["solid"], "shadow": false, "variables": {"col": 0, "row": 0}}, {"name": "Touch", "plugin": '
           '"Touch"}], "layouts": [{"name": "Game", "sheet": "Game", "layers": [{"name": "Background", "color": '
           '"canvas"}, {"name": "Board"}, {"name": "UI", "parallax": 0}], "instances": [{"object": "Cell", "layer": '
           '"Board", "col": 0, "row": 4, "repeat": [15, 15], "index": ["col", "row"]}]}], "sheets": [{"name": '
           '"Game", "events": [{"eventType": "comment", "text": "..."}, {"eventType": "block", "conditions": [...], '
           '"actions": [...]}]}]}')


class Refused(Exception):
    """The spec cannot be built; the message names the spec path and what to write."""


def refuse(where: str, what: str) -> None:
    raise Refused(f"{where}: {what}")


def keys_of(item, kind: str, where: str) -> dict:
    if not isinstance(item, dict):
        refuse(where, f"is {type(item).__name__}; it is an object {{...}} with the keys {', '.join(sorted(KEYS[kind]))}")
    unknown = sorted(set(item) - KEYS[kind])
    if unknown:
        # a key the spec has elsewhere: say where, so that it is moved there rather than dropped
        moved = [f"{k!r} belongs on {other}" for k in unknown for other in ("object", "instance", "layer", "layout")
                 if other != kind and k in KEYS[other]]
        refuse(where, f"unknown key(s) {', '.join(map(repr, unknown))}; {'an' if kind[0] in 'aeiou' else 'a'} {kind} has only "
                      f"{', '.join(sorted(KEYS[kind]))}" + (f". {'; '.join(moved)}: move it there"
                                                            + (', e.g. {"object": "Cell", ..., "visible": false} in '
                                                               "the layout's instances" if 'visible' in unknown else "")
                                                            if moved else ""))
    return item


def whole(value, where: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value) or not lo <= value <= hi:
        refuse(where, f"{value!r} is not a whole number from {lo} to {hi}")
    return int(value)


def pair(value, where: str, lo: int, hi: int) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        refuse(where, f"{value!r} is not a list of two whole numbers [width, height]")
    return whole(value[0], f"{where}[0]", lo, hi), whole(value[1], f"{where}[1]", lo, hi)


def count_events(events) -> int:
    n = 0
    for ev in events if isinstance(events, list) else []:
        if isinstance(ev, dict):
            n += 1 + len(ev.get("conditions") or []) + len(ev.get("actions") or []) + count_events(ev.get("children"))
    return n


def load_generator(rag: Path, out: Path):
    """The generator template as a module of its own, writing into out."""
    path = copilot.get_runtime().skills_root / "skills" / "construct3-agent-plugin" / "assets" / "build_project.py"
    loader = importlib.util.spec_from_file_location("c3_generator", path)
    if not loader or not path.exists():
        raise FileNotFoundError(path)
    gen = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(gen)
    gen.ROOT = out
    if bool(copilot.OPTIONS.get("quick")):
        # a quick prototype keeps a label or an outline that reads poorly instead of refusing the spec
        gen.readable = lambda *args, **kwargs: None
        gen.accent = lambda *args, **kwargs: False
        shape = gen.shape

        def lenient_shape(*args, **kwargs):
            try:
                return shape(*args, **kwargs)
            except SystemExit:
                return shape(*args, **{**kwargs, "outline": False})
        gen.shape = lenient_shape
    return gen


def set_viewport(gen, w: int, h: int) -> None:
    """What the template derives from its viewport at import, derived again for this one."""
    gen.VIEW_W, gen.VIEW_H = w, h
    gen.UNIT = 8 if h <= 360 else 32
    gen.MARGIN = gen.UNIT
    gen.TOUCH = math.ceil(48 * min(w, h) / 360 / gen.UNIT) * gen.UNIT
    gen.TEXT_SIZE = {"body": gen.UNIT, "title": 2 * gen.UNIT}
    gen.PIXEL_ART = gen.UNIT == 8
    gen.SHAPE_STYLE["outline_width"] = max(1, gen.UNIT // 4)
    gen.SHAPE_STYLE["shadow_distance"] = round(0.027 * min(w, h))


def grid(gen, rel: str, cols: int, rows: int, board: str, edge: bool, shadow: bool) -> None:
    """images/<rel>: a board of cols x rows units in the role `board`, its lines through the middle of each unit in
    the outline role, so that a piece placed on a unit sits on a crossing, the outer lines twice as thick, and the
    star points of a Go or gomoku board on an odd board of 9 or more; with the shape's hard shadow."""
    U, style = gen.UNIT, gen.SHAPE_STYLE
    w, h = cols * U, rows * U
    thin = max(1, U // 16)
    dx, dy = gen.shadow_offset() if shadow else (0, 0)
    left, top = max(0, -dx), max(0, -dy)
    iw, ih = w + abs(dx), h + abs(dy)
    first, last_x, last_y = U // 2, w - U // 2, h - U // 2
    stars = []
    if cols == rows and cols % 2 and cols >= 9:
        k = 3 if cols >= 13 else 2
        # 19 lines: nine points; 13 and 15 (gomoku): the corners and the middle; 9 to 11: the same
        stars = [(a, b) for a in (k, cols // 2, cols - 1 - k) for b in (k, cols // 2, cols - 1 - k)
                 if cols >= 19 or (a == b == cols // 2) or (a != cols // 2 and b != cols // 2)]
    radius = max(2, U // 8)
    alpha = round(255 * style["shadow_opacity"])

    def on_line(v: float, last: int) -> bool:
        width = 2 * thin if abs(v - first) < 1 or abs(v - last) < 1 else thin
        return any(abs(v - (first + i * U)) < width / 2 + 0.01 for i in range((last - first) // U + 1)) or             min(abs(v - first), abs(v - last)) < width / 2 + 0.01

    def pixel(x, y):
        px, py = x + 0.5 - left, y + 0.5 - top
        if 0 <= px < w and 0 <= py < h:
            inside_x, inside_y = first - thin <= px <= last_x + thin, first - thin <= py <= last_y + thin
            ink = (edge and min(px, py, w - px, h - py) < thin)                 or (inside_y and on_line(px, last_x)) or (inside_x and on_line(py, last_y))                 or any((px - (a * U + U / 2)) ** 2 + (py - (b * U + U / 2)) ** 2 <= radius ** 2 for a, b in stars)
            return (*gen.rgb(style["outline_role"] if ink else board), 255)
        if (dx or dy) and 0 <= px - dx < w and 0 <= py - dy < h:
            return (*gen.rgb(style["shadow_role"]), alpha)
        return (0, 0, 0, 0)

    gen.write_png(rel, iw, ih, pixel)
    poly = [round(v, 4) for cx, cy in gen.corners("rect") for v in ((left + cx * w) / iw, (top + cy * h) / ih)]
    gen.FRAMES[rel] = gen.frame(iw, ih, (left + 0.5 * w) / iw, (top + 0.5 * h) / ih, poly)
    gen.PADS[rel] = (left, top)
    gen.DRAWN_AS[rel] = ("rect", w, h, 0.5, 0.5, edge, shadow)


def walk_aces(events, where: str):
    """(path, kind, ace) for every condition and action of the events, at any depth."""
    for i, ev in enumerate(events if isinstance(events, list) else []):
        if not isinstance(ev, dict):
            continue
        at = f"{where}[{i}]"
        for kind in ("conditions", "actions"):
            for k, ace in enumerate(ev.get(kind) or []):
                if isinstance(ace, dict):
                    yield f"{at}.{kind}[{k}]", kind, ace
        yield from walk_aces(ev.get("children"), f"{at}.children")


def box_of(inst: dict) -> tuple[float, float, float, float]:
    w = inst["world"]
    left, top = w["x"] - w["originX"] * w["width"], w["y"] - w["originY"] * w["height"]
    return left, top, left + w["width"], top + w["height"]


def meet(a: tuple, b: tuple) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


def within(inner: tuple, outer: tuple) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def box_text(b: tuple) -> str:
    return f"({b[0]:g},{b[1]:g})-({b[2]:g},{b[3]:g})"


def build(spec: dict, out: Path, rag: Path) -> list[str]:
    """Write the project into out, an empty folder; return what it says about what was built."""
    keys_of(spec, "spec", "spec")
    name = spec.get("name")
    if not isinstance(name, str) or not 0 < len(name.strip()) <= 40:
        refuse("spec.name", "the project's name, 1 to 40 characters")
    gen = load_generator(rag, out)
    vw, vh = pair(spec.get("viewport", [720, 1280]), "spec.viewport", 160, 1920)
    set_viewport(gen, vw, vh)
    notes: list[str] = []
    problems: list[str] = []        # every layout problem, refused together after the layouts are built

    theme = spec.get("theme", "greybox")
    if theme not in THEMES:
        refuse("spec.theme", f"{theme!r}; the themes are {', '.join(f'{k} ({v[0]})' for k, v in THEMES.items())}")
    if THEMES[theme][1]:
        gen.PALETTE.clear()
        gen.PALETTE.update(THEMES[theme][1])
        gen.SHAPE_STYLE.update(THEMES[theme][2])
    gen.PALETTE["good"], gen.PALETTE["grey"] = GOOD[theme], GREY[theme]
    for role, colour in (spec.get("palette") or {}).items():
        if not NAME.match(str(role)) or not (isinstance(colour, list) and len(colour) == 3
                                             and all(isinstance(c, int) and 0 <= c <= 255 for c in colour)):
            refuse(f"spec.palette.{role}", "a colour role is a plain name and [red, green, blue], each 0 to 255: "
                                          '"wood": [222, 184, 135]')
        gen.PALETTE[role] = tuple(colour)
    roles = ", ".join(gen.PALETTE)

    def role(value, where: str) -> str:
        if value not in gen.PALETTE:
            refuse(where, f"{value!r} is no colour role; the roles are {roles}, or add one under spec.palette")
        return value

    # --- objects -------------------------------------------------------------------------------
    objects = spec.get("objects")
    if not isinstance(objects, list) or not 0 < len(objects) <= OBJECTS_MAX:
        refuse("spec.objects", f"a list of 1 to {OBJECTS_MAX} objects, e.g. {EXAMPLE}")
    byname: dict[str, dict] = {}
    for i, o in enumerate(objects):
        where = f"spec.objects[{i}]"
        keys_of(o, "object", where)
        oname, plugin = o.get("name"), o.get("plugin")
        if not isinstance(oname, str) or not NAME.match(oname):
            refuse(f"{where}.name", f"{oname!r}: a name is an English letter, then English letters, digits or _, up to 32, "
                                    f"e.g. \"Stone\"; the player never sees it")
        if oname in byname:
            refuse(f"{where}.name", f"{oname!r} is the name of spec.objects[{byname[oname]['_i']}] too")
        if plugin not in PLUGINS:
            refuse(f"{where}.plugin", f"{plugin!r}; the plugins here are {', '.join(PLUGINS)}")
        if plugin in SINGLE and oname != plugin:
            refuse(f"{where}.name", f"a {plugin} object is named {plugin!r}, which the events write as objectClass")
        allowed = {"Sprite": KEYS["object"], "Text": {"name", "plugin", "behaviors", "variables"},
                   "Bar": {"name", "plugin", "size", "frames"},
                   "Array": {"name", "plugin", "size"}, "Dictionary": {"name", "plugin"}}.get(plugin, {"name", "plugin"})
        extra = sorted(set(o) - allowed)
        if extra:
            refuse(where, f"a {plugin} object takes no {', '.join(map(repr, extra))}; it takes {', '.join(sorted(allowed))}")
        o = {**o, "_i": i}
        byname[oname] = o
        variables = o.get("variables") or {}
        if not isinstance(variables, dict):
            refuse(f"{where}.variables", 'name -> starting value, e.g. {"col": 0, "kind": "", "taken": false}')
        for v, init in variables.items():
            if not NAME.match(str(v)) or isinstance(init, (list, dict)) or init is None:
                refuse(f"{where}.variables.{v}", "a variable is a plain name with a number, text or true/false")
        behs = []
        for j, b in enumerate(o.get("behaviors") or []):
            b = {"name": b} if isinstance(b, str) else keys_of(b, "behavior", f"{where}.behaviors[{j}]")
            if b.get("name") not in BEHAVIORS:
                refuse(f"{where}.behaviors[{j}]", f"{b.get('name')!r}; the behaviors here are {', '.join(BEHAVIORS)}, "
                                                  f"named on the object as written, which is the behaviorType of their ACEs")
            props = dict(getattr(gen, BEHAVIORS[b["name"]][1])[b["name"]]["properties"])
            for k, v in (b.get("properties") or {}).items():
                if k not in props:
                    refuse(f"{where}.behaviors[{j}].properties.{k}", f"unknown; {b['name']} has {', '.join(props) or 'none'}")
                if type(v) is not type(props[k]) and not (isinstance(v, (int, float)) and isinstance(props[k], (int, float))
                                                          and not isinstance(v, bool)):
                    refuse(f"{where}.behaviors[{j}].properties.{k}", f"{v!r}; it is {type(props[k]).__name__} like {props[k]!r}")
                props[k] = v
            behs.append((b["name"], props))
        o["_behaviors"] = behs
        if plugin == "Sprite":
            if o.get("shape", "rect") not in SHAPES:
                refuse(f"{where}.shape", f"{o.get('shape')!r}; one of {', '.join(SHAPES)}")
            if o.get("size") == "fill":
                if o.get("shape") == "grid":
                    refuse(f"{where}.size", "a board's size is its number of cells, [15, 15]; \"fill\" is for the "
                                            "stage's one main shape")
                o["_size"] = gen.fit(1, 1)
            else:
                o["_size"] = pair(o.get("size", [1, 1]), f"{where}.size", 1, SIZE_MAX)
        if plugin in ("Sprite", "Bar"):
            frames = o.get("frames") or (["danger"] if plugin == "Bar" else ["solid"])
            if not isinstance(frames, list) or len(frames) > (1 if plugin == "Bar" else 8):
                refuse(f"{where}.frames", '["danger"], the colour of the bar\'s fill' if plugin == "Bar" else
                       'a list of 1 to 8 colour roles, one per animation frame: ["ink", "flash"]')
            o["_frames"] = [role(f, f"{where}.frames[{k}]") for k, f in enumerate(frames)]
        if plugin == "Bar":
            o["_size"] = pair(o.get("size", [6, 1]), f"{where}.size", 1, SIZE_MAX)
        if plugin == "Array":
            o["_size"] = pair(o.get("size", [10, 1]), f"{where}.size", 1, 1000)
    primary = spec.get("primary")
    if primary is not None and (primary not in byname or byname[primary]["plugin"] != "Sprite"):
        refuse("spec.primary", f"{primary!r}: the Sprite the player looks at, one of "
                               f"{', '.join(n for n, o in byname.items() if o['plugin'] == 'Sprite')}")

    # --- layouts read ahead: the screen of each, and the sizes the builder gives the shapes ----------
    layouts_in = spec.get("layouts")
    if not isinstance(layouts_in, list) or not 0 < len(layouts_in) <= LAYOUTS_MAX:
        refuse("spec.layouts", f"a list of 1 to {LAYOUTS_MAX} layouts, e.g. {EXAMPLE}")
    sheets_in = spec.get("sheets") or []
    created = set(re.findall(r'"object-to-create": "([^"]+)"', json.dumps(sheets_in)))
    screens: list[str] = []
    for li, lay in enumerate(layouts_in):
        keys_of(lay, "layout", f"spec.layouts[{li}]")
        size = lay.get("size", [vw, vh])
        screen = lay.get("screen", "stage" if size == [vw, vh] else "free")
        if screen not in ("stage", "free"):
            refuse(f"spec.layouts[{li}].screen", f"{screen!r}: \"stage\" (title, status, stage and hint bands, the "
                                                 f"default) or \"free\" (every place in units)")
        if screen == "stage" and size != [vw, vh]:
            refuse(f"spec.layouts[{li}].screen", f"a stage screen is the viewport's size, {vw} x {vh}; leave out "
                                                 f"\"size\", or write \"screen\": \"free\" for a layout that scrolls")
        screens.append(screen)
    U = gen.UNIT

    def plugin_of(inst) -> str:
        return (byname.get(inst.get("object")) or {}).get("plugin", "") if isinstance(inst, dict) else ""

    def titled(lay: dict) -> bool:
        """Whether a text of the layout is its title, so the screen keeps a title band."""
        return any(plugin_of(i) == "Text" and (i.get("band") == "title" or (i.get("anchor") == "top"
                   and i.get("size") == "title")) for i in lay.get("instances") or [])

    def number(v, mid: float) -> float | None:
        return mid if v == "center" else v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def hosts_of(li: int, inst: dict) -> list[tuple[int, float, int]]:
        """The one-copy Sprite instances a text placed by col and row lies on, its middle inside the Sprite's box,
        as (another layer, distance between the middles, index), best first: the text is meant as a Sprite's label."""
        lay = layouts_in[li]
        lw, lh = (lay.get("size") or [vw, vh])[:2]
        tw, th = inst.get("width", 8), inst.get("height", 2)
        if not all(isinstance(v, (int, float)) for v in (tw, th)):
            return []
        x, y = number(inst.get("col", 0), (lw / U - tw) / 2), number(inst.get("row", 0), (lh / U - th) / 2)
        if x is None or y is None:
            return []
        cx, cy = x + tw / 2, y + th / 2
        found = []
        for j, s in enumerate(lay.get("instances") or []):
            o = byname.get(s.get("object")) if isinstance(s, dict) else None
            if not o or o["plugin"] != "Sprite" or o.get("shape") == "grid" or s.get("repeat", [1, 1]) != [1, 1] \
                    or "label" in s or s.get("over"):
                continue
            w, h = o["_size"]
            if screens[li] == "stage":
                mc, mr = gen.stage_cell(w, h, title=titled(lay))
            else:
                mc, mr = (lw // U - w) // 2, (lh // U - h) // 2
            c, r = number(s.get("col", 0), mc), number(s.get("row", 0), mr)
            if c is not None and r is not None and c <= cx <= c + w and r <= cy <= r + h:
                found.append((int(s.get("layer") != inst.get("layer")), math.hypot(c + w / 2 - cx, r + h / 2 - cy), j))
        return sorted(found)

    labels: dict[str, list[str]] = {}
    hosts: dict[tuple[int, int], int] = {}        # (layout, text instance) -> the Sprite instance it labels
    for li, lay in enumerate(layouts_in):
        for k, inst in enumerate(lay.get("instances") or []):
            o = byname.get(inst.get("object")) if isinstance(inst, dict) else None
            if o and o["plugin"] == "Sprite" and "label" in inst:
                text = inst["label"]
                if not isinstance(text, str) or not 0 < len(text) <= 20:
                    refuse(f"spec.layouts[{li}].instances[{k}].label", "the text on the button, 1 to 20 characters")
                labels.setdefault(o["name"], []).append(str(inst.get("longest") or text))
        # each button takes the one text that lies nearest its middle, on its own layer first
        pairs = sorted((score, k, j) for k, inst in enumerate(lay.get("instances") or [])
                       if plugin_of(inst) == "Text" and not {"band", "anchor", "above", "below"} & set(inst)
                       and ("col" in inst or "row" in inst)
                       for *score, j in hosts_of(li, inst))
        for score, k, j in pairs:
            if (li, k) not in hosts and j not in {v for (m, _), v in hosts.items() if m == li}:
                inst = lay["instances"][k]
                hosts[(li, k)] = j
                labels.setdefault(lay["instances"][j]["object"], []).append(str(inst.get("longest")
                                                                                 or inst.get("text", "")))
    for oname, texts in labels.items():
        o = byname[oname]
        need = [math.ceil(v / gen.UNIT) for v in gen.button_size(max(texts, key=gen.text_ems))]
        grown = (max(o["_size"][0], need[0]), max(o["_size"][1], need[1]))
        if grown != o["_size"]:
            notes.append(f"{oname} drawn at {grown[0]} x {grown[1]} units to hold its label")
            o["_size"] = grown
    moving = {"8Direction", "Platform", "Bullet", "MoveTo", "DragDrop", "Sine", "Rotate", "ScrollTo"}
    for li, lay in enumerate(layouts_in):
        shown = [inst for inst in lay.get("instances") or [] if isinstance(inst, dict)
                 and (byname.get(inst.get("object")) or {}).get("plugin") == "Sprite" and inst.get("visible") is not False]
        if screens[li] != "stage" or len(shown) != 1:
            continue
        inst, o = shown[0], byname[shown[0]["object"]]
        if (inst.get("col") == "center" and inst.get("row") == "center" and inst.get("repeat", [1, 1]) == [1, 1]
                and o.get("shape") != "grid" and o["name"] not in created
                and not moving & {b for b, _ in o["_behaviors"]}):
            target = gen.fit(*o["_size"], title=titled(lay))
            if target[0] > o["_size"][0] and target[1] > o["_size"][1]:
                notes.append(f"{o['name']} drawn at {target[0]} x {target[1]} units, as large as the stage allows, "
                             f"its proportions kept")
                o["_size"] = target

    # --- images and object types ---------------------------------------------------------------
    U = gen.UNIT
    files: dict[str, list[str]] = {}
    types: dict[str, dict] = {}
    for oname, o in byname.items():
        where = f"spec.objects[{o['_i']}]"
        behaviors = [gen.beh_def(BEHAVIORS[b][0], b) for b, _ in o["_behaviors"]]
        ivars = [gen.ivar_def(v, "boolean" if isinstance(x, bool) else "number" if isinstance(x, (int, float)) else "string")
                 for v, x in (o.get("variables") or {}).items()]
        plugin = o["plugin"]
        if plugin == "Sprite":
            w, h = o["_size"]
            # The template's outline and shadow follow the grid unit, so a one-unit shape is a quarter outline
            # and its shadow half its size; here they follow the shape's shorter side unless the spec gives px.
            side = min(w, h) * U
            line, drop = o.get("outline", True), o.get("shadow", True)
            widest, farthest = max(1, U // 4), gen.SHAPE_STYLE["shadow_distance"]
            if line is not True and line is not False and (isinstance(line, bool) or line not in range(1, widest + 1)):
                refuse(f"{where}.outline", f"{line!r}: true, false, or the outline's width in px from 1 to {widest}")
            if drop is not True and drop is not False and (isinstance(drop, bool) or drop not in range(1, farthest + 1)):
                refuse(f"{where}.shadow", f"{drop!r}: true, false, or the shadow's distance in px from 1 to {farthest}")
            outline_role = role(o.get("outline_color", gen.SHAPE_STYLE["outline_role"]), f"{where}.outline_color")
            if line is not False:
                # the outline is the spec's colour when it reads on every frame of the shape, else the builder's
                def worst(r: str) -> float:
                    return min(gen.contrast(gen.PALETTE[r], gen.rgb(f)) for f in o["_frames"])
                if outline_role in o["_frames"] or worst(outline_role) < 3:
                    outline_role = max((r for r in gen.PALETTE if r not in o["_frames"]), key=worst)
            style = dict(gen.SHAPE_STYLE)
            gen.SHAPE_STYLE.update({
                "outline_width": min(widest, max(1, round(side / 16))) if line is True else line or widest,
                "outline_role": outline_role,
                "shadow_distance": min(farthest, max(1, round(side / 12))) if drop is True else drop or farthest})
            files[oname] = []
            try:
                for k, colour in enumerate(o["_frames"]):
                    rel = f"{oname.lower()}-default-{k:03d}.png"
                    try:
                        if o.get("shape") == "grid":
                            grid(gen, rel, w, h, colour, edge=line is not False, shadow=drop is not False)
                        else:
                            gen.shape(rel, o.get("shape", "rect"), w * U, h * U, colour, outline=line is not False,
                                      shadow=drop is not False)
                    except SystemExit as e:
                        reads = [r for r in gen.PALETTE if gen.contrast(gen.PALETTE[r], gen.rgb(colour)) >= 3]
                        refuse(f"{where}.frames[{k}]", f"{e}. Or keep the colour and set \"outline_color\" to one "
                                                       f"that reads on it, {', '.join(reads) or 'none'}, or \"outline\": false")
                    files[oname].append(rel)
            finally:
                gen.SHAPE_STYLE.update(style)
            frames = [dict(gen.drawn(rel)) for rel in files[oname]]
            types[oname] = gen.sprite_type(oname, [gen.animation("Default", frames)], ivars, behaviors)
        elif plugin == "Text":
            types[oname] = gen.text_type(oname, ivars, behaviors)
        elif plugin == "Bar":
            gen.bar_images(f"{oname}Frame", oname, frame_role="canvas_alt", fill_role=o["_frames"][0], caps=True)
            types.update(gen.bar_types(f"{oname}Frame", oname, caps=True))
        elif plugin in NONWORLD:
            types[oname] = gen.nonworld_type(oname, NONWORLD[plugin])
        else:
            types[oname] = gen.single_global_type(oname, plugin, dict(SINGLE[plugin]))
    for oname in labels:
        label = f"{oname}Label"
        if label in byname and byname[label]["plugin"] != "Text":
            refuse(f"spec.objects[{byname[label]['_i']}]", f"{label} holds the label of {oname}, so it is a Text, or "
                   f"give this object another name")
        if label not in types:
            types[label] = gen.text_type(label)
            notes.append(f"{oname}'s label is the Text {label}: Set text on {label} changes it, and it moves, hides "
                         f"and is destroyed with {oname}")

    # --- sheets ----------------------------------------------------------------------------------
    if not isinstance(sheets_in, list):
        refuse("spec.sheets", 'a list of sheets, {"name": "Game", "events": [...]}')
    sheet_names = []
    for s, sh in enumerate(sheets_in):
        if isinstance(sh, dict) and "eventType" in sh and s:
            refuse(f"spec.sheets[{s}]", f"is an event, not a sheet: the \"events\" list of spec.sheets[{s - 1}] was "
                   f"closed with ] before it. Move it, and any event after it, back inside that list")
        keys_of(sh, "sheet", f"spec.sheets[{s}]")
        if not isinstance(sh.get("name"), str) or not SHEET_NAME.match(sh["name"]) or sh["name"] in sheet_names:
            refuse(f"spec.sheets[{s}].name", f"{sh.get('name')!r}: " + ("another sheet has this name" if sh.get("name") in sheet_names
                   else "a name is English letters, digits, _ and spaces, starting with a letter, e.g. \"Game\"; the "
                        "player never sees it"))
        if not isinstance(sh.get("events", []), list):
            refuse(f"spec.sheets[{s}].events", "a list of events as edit_sheet writes them")
        sheet_names.append(sh["name"])
    if sum(count_events(sh.get("events")) for sh in sheets_in) > EVENTS_MAX:
        refuse("spec.sheets", f"more than {EVENTS_MAX} events, conditions and actions; make the game smaller")
    tapped: dict[str, str] = {}
    tinted: dict[str, list[str]] = {}
    for s, sh in enumerate(sheets_in):
        for path, kind, ace in walk_aces(sh.get("events"), f"spec.sheets[{s}].events"):
            obj = (ace.get("parameters") or {}).get("object")
            if kind == "conditions" and ace.get("id") in TAP_CONDITIONS and obj in byname:
                tapped.setdefault(obj, path)
            o = byname.get(ace.get("objectClass"))
            if kind == "actions" and ace.get("id") == "set-default-color" and o and o["plugin"] == "Sprite" \
                    and any(f != "flash" for f in o["_frames"]):
                tinted.setdefault(o["name"], []).append(path)
    for oname, paths in tinted.items():
        o, path = byname[oname], ", ".join(paths)
        problems.append(
            f"{path}: Set color multiplies {oname}'s image, drawn in {', '.join(o['_frames'])}, so a colour set on it "
            f"comes out darker than written. Draw one frame per state instead: spec.objects[{o['_i']}].frames "
            f"[{json.dumps(o['_frames'][0])}, \"<role of the other state>\"] (add the role under spec.palette), and "
            f"in place of each Set color {{\"id\": \"set-animation-frame\", \"objectClass\": \"{oname}\", "
            f"\"parameters\": {{\"frame-number\": \"1\"}}}} (\"0\" for the first state). A colour chosen while the "
            f"game runs needs a white image, \"frames\": [\"flash\"], which Set color tints exactly")

    # --- layouts -------------------------------------------------------------------------------
    layouts: dict[str, dict] = {}
    placed: set[str] = set()
    origin: dict[int, tuple[str, dict]] = {}      # uid -> (spec path, spec instance) of each instance made here
    total = 0
    for li, lay in enumerate(layouts_in):
        where = f"spec.layouts[{li}]"
        screen = screens[li]
        lname = lay.get("name")
        if not isinstance(lname, str) or not SHEET_NAME.match(lname) or lname in layouts or lname == "Objects":
            refuse(f"{where}.name", f"{lname!r}: a name no other layout has, not \"Objects\"; English letters, digits, _ "
                                    f"and spaces, e.g. \"Game\"")
        sheet = lay.get("sheet")
        if sheet is not None and sheet not in sheet_names:
            refuse(f"{where}.sheet", f"{sheet!r} is not in spec.sheets, which has {', '.join(sheet_names) or 'none'}; "
                                     f"add {{\"name\": {json.dumps(sheet)}, \"events\": []}} there")
        lw, lh = pair(lay.get("size", [vw, vh]), f"{where}.size", 160, 20000)
        layers_in = lay.get("layers") or [{"name": "Background", "color": "canvas"}, {"name": "Game"},
                                          {"name": "UI", "parallax": 0}]
        layers = []
        for k, ly in enumerate(layers_in):
            keys_of(ly, "layer", f"{where}.layers[{k}]")
            if not isinstance(ly.get("name"), str) or not SHEET_NAME.match(ly["name"]):
                refuse(f"{where}.layers[{k}].name", f"{ly.get('name')!r}: a layer name is English letters, digits, _ and "
                                                    f"spaces, e.g. \"Game\"")
            colour = role(ly["color"], f"{where}.layers[{k}].color") if "color" in ly else None
            par = ly.get("parallax", 1)
            if par not in (0, 1):
                refuse(f"{where}.layers[{k}].parallax", "1 for the world, 0 for a HUD layer that stays put")
            layers.append(gen.layer(ly["name"], bg=colour, transparent=colour is None, parallax=par))
        by_layer = {ly["name"]: ly for ly in layers}
        backdrop_role = next((ly["color"] for ly in layers_in if "color" in ly), "canvas")
        nonworld = [gen.nonworld_inst(n, {"width": o["_size"][0], "height": o["_size"][1], "depth": 1}
                                      if o["plugin"] == "Array" else {})
                    for n, o in byname.items() if o["plugin"] in NONWORLD and not li]
        made = gen.layout(lname, layers, sheet, nonworld, lw, lh)
        if lay.get("backdrop"):
            if "Backdrop" not in types:
                gen.pattern("Backdrop", "checker")
                types["Backdrop"] = gen.pattern_type("Backdrop")
            made["layers"][0]["instances"].append(gen.backdrop("Backdrop", lw, lh))
        rects: list[tuple] = []
        taken: dict[str, list[tuple[str, tuple]]] = {}   # band -> (name, box) of what it holds
        band_texts: dict[str, list[tuple[dict, str, bool]]] = {}   # band -> (text instance, spec path, starts empty)
        has_title = titled(lay)
        bands = gen.bands("stage", has_title) if screen == "stage" else {}
        stage = bands.get("stage")
        made_at: dict[int, tuple[dict, list]] = {}    # spec index of a one-copy Sprite -> (its instance, its layer's list)
        # Buttons of one layer that all ask for the middle, with no shift, lie exactly on each other, which hides
        # all but one: a column or a partial overlap is the spec's choice, so the refusal gives the values of both.
        for layer_name in {i.get("layer") for i in lay.get("instances") or [] if isinstance(i, dict)}:
            mids = [(k, byname[i["object"]]["_size"]) for k, i in enumerate(lay.get("instances") or [])
                    if plugin_of(i) == "Sprite" and "label" in i and i.get("layer") == layer_name
                    and i.get("col") == "center" and i.get("row") == "center" and i.get("repeat", [1, 1]) == [1, 1]
                    and not i.get("dx") and not i.get("dy")]
            if len(mids) < 2:
                continue
            col_h = sum(h for _, (w, h) in mids) + len(mids) - 1
            top = gen.stage_cell(1, col_h, title=has_title)[1] if screen == "stage" else (lh // U - col_h) // 2
            rows = []
            for k, (w, h) in mids:
                rows.append(f"{lay['instances'][k]['object']} \"row\": {top}")
                top += h + 1
            last = lay["instances"][mids[-1][0]]["object"]
            problems.append(f"{where}.instances[{', '.join(str(k) for k, _ in mids)}]: "
                            f"{', '.join(lay['instances'][k]['object'] for k, _ in mids)} all sit in the middle of layer "
                            f"{layer_name} and cover each other exactly. For a column, a unit apart: {', '.join(rows)}, "
                            f"\"col\": \"center\" on each. To overlap them partly: \"dx\": 2, \"dy\": 1 on {last}")
        stacked: dict[int, tuple[int, int]] = {}
        unbanded: list[tuple[str, str]] = []

        def keep(inst_made: dict, path: str, inst: dict) -> dict:
            origin[inst_made["uid"]] = (path, inst)
            return inst_made

        # the shapes first, so a text can be placed on, above or below any of them; a text draws over them
        order = sorted(enumerate(lay.get("instances") or []), key=lambda kv: plugin_of(kv[1]) == "Text")
        for k, inst in order:
            iw = f"{where}.instances[{k}]"
            keys_of(inst, "instance", iw)
            o = byname.get(inst.get("object"))
            if not o:
                refuse(f"{iw}.object", f"{inst.get('object')!r} is not in spec.objects, which has {', '.join(byname)}")
            if o["plugin"] not in (*WORLD, "Bar"):
                refuse(f"{iw}.object", f"a {o['plugin']} is not placed in a layout; leave it out of instances")
            if inst.get("layer") not in by_layer:
                refuse(f"{iw}.layer", f"{inst.get('layer')!r}; the layers of this layout are {', '.join(by_layer)}")
            target = by_layer[inst["layer"]]["instances"]
            placed.add(o["name"])
            declared = o.get("variables") or {}
            given = inst.get("variables") or {}
            for v in given:
                if v not in declared:
                    refuse(f"{iw}.variables.{v}", f"{o['name']} has no variable {v!r}; declare it in "
                                                  f"spec.objects[{o['_i']}].variables first")
            behaviors = {b: {"properties": props} for b, props in o["_behaviors"]}
            on_default = backdrop_role if by_layer[inst["layer"]]["isTransparent"] else \
                next(ly.get("color", "canvas") for ly in layers_in if ly["name"] == inst["layer"])
            if "label" in inst and o["plugin"] == "Text":
                refuse(f"{iw}.label", "a label goes on a Sprite or a Bar; this Text shows \"text\"")

            if o["plugin"] == "Bar":
                length, height = o["_size"][0] * U, o["_size"][1] * U
                extra = sorted(set(inst) - {"object", "layer", "label", "band", "align", "anchor", "dx", "dy", "visible"})
                if extra:
                    refuse(iw, f"a Bar is placed by \"band\" and \"align\" (or \"anchor\" on a free screen), with its "
                               f"name in \"label\"; leave out {', '.join(map(repr, extra))}")
                text = inst.get("label")
                lw_, lh_ = gen.label_box(text) if text else (0, 0)
                box_w, box_h = (lw_ + U if text else 0) + length, max(lh_, height)
                if screen == "stage":
                    band, align = band_on_edge(inst.get("band")) or (inst.get("band", "status"), "left")
                    align = inst.get("align", align)
                    if band not in bands or align not in ("left", "center", "right"):
                        refuse(iw, f"\"band\" one of {', '.join(bands)}, \"align\" left, center or right")
                    bx, by, bwid, bh = bands[band]
                    if box_w > bwid:
                        problems.append(f"{iw}: {o['name']} with its label is {box_w // U} units long and the {band} band "
                                        f"holds {bwid // U}; set spec.objects[{o['_i']}].size [{max(1, (bwid - box_w + length) // U)}, "
                                        f"{o['_size'][1]}]")
                        continue
                    x = {"left": bx, "center": bx + (bwid - box_w) // 2, "right": bx + bwid - box_w}[align]
                    y = by + (bh - box_h) // 2
                else:
                    x, y = gen.anchor(inst.get("anchor", "top-left"), box_w, box_h, 0, 0, inst.get("dx", 0), inst.get("dy", 0))
                made_bar = gen.bar_at(f"{o['name']}Frame", o["name"], x + box_w - length / 2, y + box_h / 2, length, height,
                                      caps=True)
                if screen == "stage":
                    taken.setdefault(band, []).append((o["name"], (x, y, x + box_w, y + box_h)))
                if text:
                    colour = gen.text_on(on_default)
                    target.append(keep(gen.text_inst(f"{o['name']}Label", text, x, y, lw_, box_h, halign="left", bold=True,
                                                     color=colour, on=on_default), iw, inst))
                    if f"{o['name']}Label" not in types:
                        types[f"{o['name']}Label"] = gen.text_type(f"{o['name']}Label")
                for part in made_bar:
                    part["properties"]["initially-visible"] = inst.get("visible", True) is not False
                    target.append(keep(part, iw, inst))
                notes.append(f"{o['name']} is a bar {length - 4} px long when full, its fill the Tiled Background "
                             f"{o['name']}: Set width of {o['name']} to {length - 4} * value / most")
                total += 1
                continue

            if o["plugin"] == "Text":
                text = inst.get("text", "")
                if not isinstance(text, str) or len(text) > 200:
                    refuse(f"{iw}.text", "the text it starts with, up to 200 characters")
                size = gen.TEXT_SIZE.get(inst.get("size", "body"))
                if size is None:
                    refuse(f"{iw}.size", '"body" for a label, "title" for a banner')
                on = role(inst.get("on", on_default), f"{iw}.on")
                colour = role(inst.get("color", "ink"), f"{iw}.color")
                if gen.contrast(gen.rgb(colour), gen.rgb(on)) < gen.text_contrast(size):
                    colour = gen.text_on(on, size)
                longest = str(inst.get("longest") or text)
                fits = (vw - 2 * gen.MARGIN) // U
                ivars = {**declared, **given}
                near = inst.get("below") or inst.get("above")
                anchor_ = inst.get("anchor")
                band = None if near else inst.get("band")    # "below" a Sprite says more than a band
                if band_on_edge(band):
                    band, side = band_on_edge(band)
                    inst = {**inst, "align": inst.get("align", side)}
                if (li, k) in hosts and hosts[(li, k)] in made_at:
                    # a text laid on a button is its label: centred on the button's box, and its child
                    host, host_list, hc, hr, hw, hh, fill = made_at[hosts[(li, k)]]
                    if "size" not in inst:
                        size = gen.label_size(longest, hw * U, hh * U)
                    need = gen.label_box(longest, size)[0]
                    if need > hw * U:
                        problems.append(f"{iw}: {o['name']} lies on {host['type']} as its label, and {longest!r} is "
                                        f"{math.ceil(need / U)} units wide on a button {hw} wide; set spec.objects"
                                        f"[{byname[host['type']]['_i']}].size [{math.ceil(need / U) + 2}, {hh}], or "
                                        f"shorten the text")
                        continue
                    label = gen.text_inst(o["name"], text, hc * U, hr * U, hw * U, hh * U, size, "center", bold=True,
                                          color=gen.text_on(fill, size), on=fill, ivars=ivars, behaviors=behaviors)
                    gen.link(host, label)
                    host_list.append(keep(label, iw, inst))
                    notes.append(f"{o['name']} placed on {host['type']} as its label: it moves, hides and is destroyed "
                                 f"with {host['type']}")
                    total += 1
                    continue
                if screen == "stage" and not near and not band:
                    if anchor_:
                        band, align = ANCHOR_BANDS.get(anchor_, (None, None))
                        if band == "status" and anchor_ == "top" and size == gen.TEXT_SIZE["title"]:
                            band = "title"
                        if band is None:
                            refuse(f"{iw}.anchor", f"{anchor_!r}; one of {', '.join(ANCHOR_BANDS)}")
                    else:
                        unbanded.append((iw, o["name"]))
                        continue
                    inst = {**inst, "band": band, "align": inst.get("align", align)}
                if band and screen != "stage":
                    refuse(f"{iw}.band", "bands are on a stage screen; on this free screen place a text with "
                                         "\"anchor\", or col and row")
                try:
                    if band:
                        # the side asked for, else another side of a status or hint line where the text fits
                        align = inst.get("align", "center")
                        sides = [align] + ([a for a in ("left", "right", "center") if a != align]
                                           if band in ("status", "hint") else [])
                        made_inst = None
                        for side in sides:
                            made_inst = gen.band_text(o["name"], text, band, side, longest, title=has_title,
                                                      color=colour, on=on, ivars=ivars, behaviors=behaviors)
                            if not any(meet(box_of(made_inst), b) for _, b in taken.get(band, [])):
                                break
                            made_inst = None
                        if made_inst is None:
                            empty = [b for b in bands if b not in taken and b != band]
                            problems.append(f"{iw}: the {band} band has no room for {o['name']} beside "
                                            f"{', '.join(n for n, _ in taken[band])}; put it in the "
                                            + (f"{empty[0]} band, which is empty" if empty else
                                               "band of another, or shorten the texts")
                                            + (", or \"below\"/\"above\" a Sprite" if band != "stage" else ""))
                            continue
                        if side != align:
                            notes.append(f"{o['name']} placed at the {side} of the {band} band, beside "
                                         f"{', '.join(n for n, _ in taken[band])}")
                        taken.setdefault(band, []).append((o["name"], box_of(made_inst)))
                        band_texts.setdefault(band, []).append((made_inst, iw, not longest.strip()))
                    elif near:
                        side = "below" if "below" in inst else "above"
                        box = next((r for r in rects if r[1]["name"] == near), None)
                        if not box:
                            refuse(f"{iw}.{side}", f"{near!r} is no Sprite placed earlier in this layout's instances; "
                                                   f"name one placed above this entry")
                        _, _, bc, br, bw, bh, _ = box
                        tw, th = gen.label_box(longest, size)
                        if not longest.strip():
                            tw = fits * U        # it starts empty: as wide as the screen, for what the events write
                        if tw > fits * U:
                            per = gen.text_ems("字") * size * gen.PX_PER_PT / U
                            problems.append(f"{iw}: the text {longest!r} is {tw // U} units wide at this size and the "
                                            f"viewport holds {fits} inside its margins, about {int(fits / per)} Chinese "
                                            f"characters; shorten \"text\" and \"longest\""
                                            + (', or "size": "body"' if size != gen.TEXT_SIZE["body"] else ""))
                            continue
                        top_edge = stage[1] if stage else gen.MARGIN
                        bottom_edge = stage[1] + stage[3] if stage else lh - gen.MARGIN
                        below_y, above_y = (br + bh + 1) * U, (br - 1) * U - th
                        y = below_y if side == "below" else above_y
                        if side == "above" and y < top_edge and below_y + th <= bottom_edge:
                            y, side = below_y, "below"
                            notes.append(f"{o['name']} placed below {near}: above it there is no room")
                        elif side == "below" and y + th > bottom_edge and above_y >= top_edge:
                            y, side = above_y, "above"
                            notes.append(f"{o['name']} placed above {near}: below it there is no room")
                        x = min(max(gen.MARGIN, (bc + bw / 2) * U - tw / 2), vw - gen.MARGIN - tw)
                        made_inst = gen.text_inst(o["name"], text, x, y, tw, th, size, "center", color=colour, on=on,
                                                  ivars=ivars, behaviors=behaviors)
                    elif anchor_:
                        tw = gen.label_box(longest, size)[0]
                        if tw > fits * U:
                            problems.append(f"{iw}: the text {longest!r} is {tw // U} units wide and the viewport holds "
                                            f"{fits} inside its margins; shorten \"text\" and \"longest\"")
                            continue
                        made_inst = gen.hud_text(o["name"], text, anchor_, size, inst.get("longest"), color=colour,
                                                 on=on, dx=inst.get("dx", 0), dy=inst.get("dy", 0),
                                                 ivars=ivars, behaviors=behaviors)
                    else:
                        col, row = whole(inst.get("col", 0), f"{iw}.col", 0, 600), whole(inst.get("row", 0), f"{iw}.row", 0, 600)
                        tw = whole(inst.get("width", 8), f"{iw}.width", 1, 60)
                        th = whole(inst.get("height", 2), f"{iw}.height", 1, 60)
                        align = inst.get("align", "left")
                        if align not in ("left", "center", "right"):
                            refuse(f"{iw}.align", "left, center or right")
                        if (col + tw) * U > lw:
                            problems.append(f"{iw}: col {col} plus width {tw} reaches past the layout's {lw // U} "
                                            f"units; make them add up to {lw // U} at most")
                            continue
                        need = gen.label_box(longest, size)[0]
                        if need > tw * U:
                            problems.append(f"{iw}: the text {longest!r} needs width {math.ceil(need / U)} units and "
                                            f"has {tw}; set \"width\": {math.ceil(need / U)}" + (
                                                f" and \"col\": {max(0, lw // U - math.ceil(need / U))}"
                                                if (col + math.ceil(need / U)) * U > lw else ""))
                            continue
                        made_inst = gen.text_inst(o["name"], text, col * U, row * U, tw * U, th * U, size, align,
                                                  color=colour, on=on, ivars=ivars, behaviors=behaviors)
                except SystemExit as e:
                    problems.append(f"{iw}: " + f"{e}".replace("hud_text()", "anchor").replace("band_text()", "band")
                                    .replace("on=", '"on"'))
                    continue
                made_inst["properties"]["initially-visible"] = inst.get("visible", True) is not False
                target.append(keep(made_inst, iw, inst))
                total += 1
                continue

            board = inst.get("over")
            if board:
                # tap targets laid over a board: one per square, the board's corner and size, nothing to compute
                box = next((r for r in rects if r[1]["name"] == board and r[1].get("shape") == "grid"), None)
                if not box:
                    refuse(f"{iw}.over", f"{board!r} is no grid object placed earlier in this layout's instances; "
                                         f"place the board first, then this entry")
                w, h = o["_size"]
                if box[4] % w or box[5] % h:
                    refuse(f"{iw}.over", f"the board is {box[4]} x {box[5]} units and {o['name']} {w} x {h}; give "
                                         f"{o['name']} \"size\": [1, 1]")
                extra = sorted(set(inst) & {"col", "row", "repeat", "gap"})
                if extra:
                    refuse(iw, f"\"over\" places it; leave out {', '.join(map(repr, extra))}")
                inst = {**inst, "col": box[2], "row": box[3], "repeat": [box[4] // w, box[5] // h],
                        "visible": inst.get("visible", False)}
            cols, rows = pair(inst.get("repeat", [1, 1]), f"{iw}.repeat", 1, 100)
            if "label" in inst and (cols, rows) != (1, 1):
                refuse(f"{iw}.label", "a labelled Sprite is one button; write one instance per button, each with its "
                                      "label, instead of a repeat")
            gap = whole(inst.get("gap", 0), f"{iw}.gap", 0, 20)
            index = inst.get("index") or []
            if not isinstance(index, list) or len(index) > 2 or any(v not in declared for v in index):
                refuse(f"{iw}.index", f"up to two variables of {o['name']}, [column, row], that get each copy's "
                                      f"place in the repeat from 0; declared: {', '.join(declared) or 'none'}")
            frame = whole(inst.get("frame", 0), f"{iw}.frame", 0, len(o["_frames"]) - 1)
            w, h = o["_size"]
            span_w, span_h = cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap
            room_w, room_h = lw // U, lh // U
            # "center" puts the whole repeat in the middle of the stage, or of the layout on a free screen
            mid_c, mid_r = (gen.stage_cell(span_w, span_h, title=has_title) if stage
                            else ((room_w - span_w) // 2, (room_h - span_h) // 2))
            col0 = mid_c if inst.get("col") == "center" else whole(inst.get("col", 0), f"{iw}.col", 0, 600)
            row0 = mid_r if inst.get("row") == "center" else whole(inst.get("row", 0), f"{iw}.row", 0, 600)
            col0, row0 = stacked.get(k, (col0, row0))
            # "dx" and "dy" shift a shape by whole units from where col and row put it
            col0 += whole(inst.get("dx", 0), f"{iw}.dx", -100, 100)
            row0 += whole(inst.get("dy", 0), f"{iw}.dy", -100, 100)
            if col0 < 0 or col0 + span_w > room_w or row0 < 0 or row0 + span_h > room_h:
                problems.append(f"{iw}: {o['name']} covers columns {col0} to {col0 + span_w - 1} and rows {row0} to "
                                f"{row0 + span_h - 1}, and the layout is {room_w} x {room_h} units; it must fit: a smaller "
                                f"size or repeat, another col or row, or \"col\": \"center\" to centre it")
                continue
            rects.append((iw, o, col0, row0, span_w, span_h, inst.get("visible", True) is not False))
            total += cols * rows
            if total > INSTANCES_MAX:
                refuse(iw, f"more than {INSTANCES_MAX} instances in all; make the repeat smaller")
            for r in range(rows):
                for c in range(cols):
                    ivars = {**declared, **given}
                    for v, n in zip(index, (c, r)):
                        ivars[v] = n
                    at = (col0 + c * (w + gap), row0 + r * (h + gap))
                    if "label" in inst:
                        made_inst, label = gen.button(o["name"], files[o["name"]][frame], f"{o['name']}Label",
                                                      inst["label"], *at, longest=inst.get("longest"), ivars=ivars,
                                                      behaviors=behaviors)
                    else:
                        made_inst = gen.shape_inst(o["name"], files[o["name"]][0], *at, ivars=ivars, behaviors=behaviors)
                    made_inst["properties"]["initial-frame"] = frame
                    made_inst["properties"]["initially-visible"] = inst.get("visible", True) is not False
                    target.append(keep(made_inst, iw, {**inst, "_row": row0, "_col": col0}))
                    if "label" in inst:
                        label["properties"]["initially-visible"] = made_inst["properties"]["initially-visible"]
                        target.append(keep(label, iw, inst))
                    elif (cols, rows) == (1, 1):
                        made_at[k] = (made_inst, target, col0, row0, w, h, o["_frames"][frame])
        # A label alone in its band gets the band's width, so a longer text the events write still fits.
        for band, held in taken.items():
            texts = band_texts.get(band, [])
            if len(held) == 1 and texts:
                texts[0][0]["world"]["x"], texts[0][0]["world"]["width"] = bands[band][0], bands[band][2]
            elif len(held) == len(texts) and all(not blank for _, _, blank in texts):
                # labels that share a band share its width, left to right, a unit apart, each as wide as it can be
                slot = (bands[band][2] - (len(texts) - 1) * U) // len(texts)
                order = sorted(texts, key=lambda t: t[0]["world"]["x"])
                if all(t["world"]["width"] <= slot for t, _, _ in order):
                    for n, (t, _, _) in enumerate(order):
                        t["world"]["x"], t["world"]["width"] = bands[band][0] + n * (slot + U), slot
            else:
                problems.extend(f"{path}: {t['type']} starts empty and shares the {band} band, so its box has no width; "
                                f"give it \"longest\", the widest text the events write" for t, path, blank in texts if blank)
        if unbanded:
            problems.append(f"{', '.join(p for p, _ in unbanded)}: {', '.join(n for _, n in unbanded)} placed by col and "
                            f"row, and this screen puts a text in a band by name: \"band\": \"status\" for what the "
                            f"player watches (score, time), \"title\" for the name, \"hint\" for what to do, \"stage\" "
                            f"for a big line in the middle; or \"above\"/\"below\" a Sprite; or, for a button, a Sprite "
                            f"with the text as its \"label\". Leave out col, row, width and height")
        # A board's picture and the tap targets over it are one grid: the same corner and the same size.
        for gw, g, gc, gr, gsw, gsh, _ in (r for r in rects if r[1].get("shape") == "grid"):
            for tw_, t, tc, tr, tsw, tsh, shown in rects:
                overlaps = min(gc + gsw, tc + tsw) > max(gc, tc) and min(gr + gsh, tr + tsh) > max(gr, tr)
                if t is not g and not shown and overlaps and (tc, tr, tsw, tsh) != (gc, gr, gsw, gsh):
                    refuse(tw_, f"the tap targets {t['name']} cover {tsw} x {tsh} units from column {tc}, row {tr}, "
                                f"and the board {g['name']} ({gw}) {gsw} x {gsh} from column {gc}, row {gr}; a piece "
                                f"then misses a crossing. Give both the same corner and size: {t['name']} \"repeat\" "
                                f"[{gsw // t['_size'][0]}, {gsh // t['_size'][1]}] at the board's col and row, the board's "
                                f"\"size\" equal to the repeat")
        for k, ly in enumerate(made["layers"]):
            if ly["parallaxX"] == 0:
                try:
                    # a button's label lies inside its button, so the button speaks for both
                    gen.no_overlap([i for i in ly["instances"] if not (i.get("sceneGraphData") or {}).get("parent-uid")],
                                   f"{where}.layers[{k}] ({ly['name']})")
                except SystemExit as e:
                    for said in str(e).splitlines():
                        said = re.sub(r"; place it with anchor\(\) or row\(\)[^.]*|: dy=\d+ on its anchor\(\)[^.]*|\. Or size a .*",
                                      "", said)
                        moved = re.search(r"Move (\w+) down (\d+) units", said)
                        sprite = next((origin[i["uid"]] for i in ly["instances"] if moved and i["type"] == moved[1]
                                       and isinstance(origin.get(i["uid"], ("", {}))[1].get("_row"), int)
                                       and origin[i["uid"]][1].get("row") != "center"), None)
                        if sprite:
                            problems.append(f"{said[:moved.end()]}: \"row\": {sprite[1]['_row'] + int(moved[2])} at "
                                            f"{sprite[0]}, or a smaller \"size\"")
                        else:
                            problems.append(f"{said}. In the spec: a \"dy\" on the instance moves it down whole units, "
                                            f"a shorter \"text\" and \"longest\" narrow a label, or another \"anchor\" or "
                                            f"\"band\"")
        layouts[lname] = made

    # A created copy takes the properties of the object's instance in a layout: an invisible one makes every copy
    # invisible.
    for li, lay in enumerate(layouts_in):
        for k, inst in enumerate(lay.get("instances") or []):
            if inst.get("object") in created and inst.get("visible") is False:
                problems.append(f"spec.layouts[{li}].instances[{k}]: the events create {inst['object']}, and a created "
                                f"copy takes this instance's properties, so every copy would be invisible. Leave "
                                f"{inst['object']} out of instances: an object with none gets its template in a layout "
                                f"that never runs")
    # What the player sees, as numbers: every text inside the screen, no text on a shape it is not the label of
    # and no two texts on each other, a tapped shape a finger's width, the main object the one that stands out.
    for lname, lay in layouts.items():
        boxes = []
        for ly in lay["layers"]:
            for inst in ly["instances"]:
                if inst.get("world") and inst["properties"].get("initially-visible", True) and inst["type"] != "Backdrop":
                    boxes.append((inst, box_of(inst), "text" in inst["properties"], ly["parallaxX"] == 0))
        lw_, lh_ = lay["width"], lay["height"]
        for inst, b, is_text, hud in boxes:
            limit = (vw, vh) if hud else (lw_, lh_)
            if is_text and (b[0] < 0 or b[1] < 0 or b[2] > limit[0] or b[3] > limit[1]):
                path = origin.get(inst["uid"], (f"layout {lname}",))[0]
                problems.append(f"{path}: the text {inst['type']} {box_text(b)} reaches past the {'viewport' if hud else 'layout'} "
                                f"{limit[0]}x{limit[1]}; " + (f"move it {math.ceil(-b[1] / U)} units down" if b[1] < 0 else
                                f"move it {math.ceil((b[3] - limit[1]) / U)} units up" if b[3] > limit[1] else
                                "shorten its \"text\" and \"longest\"") + ", or put it in a band")
        for i, (t, tb, is_text, _) in enumerate(boxes):
            if not is_text:
                continue
            for j, (s, sb, s_text, _hud) in enumerate(boxes):
                if j == i or (s_text and j < i) or not meet(tb, sb) or (not s_text and within(tb, sb)):
                    continue
                if all((x.get("sceneGraphData") or {}).get("parent-uid") for x in (t, s)):
                    continue        # two labels meet where their buttons do, which the buttons' problem names
                tpath, sinst = origin.get(t["uid"], (f"layout {lname}",)), origin.get(s["uid"], (f"layout {lname}", {}))
                rows_down = math.ceil((tb[3] + U - sb[1]) / U)
                if s_text:
                    fix = (f"put {s['type']} in another band or \"align\", or {rows_down} units lower with \"dy\", or "
                           f"shorten their texts")
                elif isinstance(sinst[1].get("_row"), int) and sinst[1].get("row") != "center":
                    fix = (f"move {s['type']} down {rows_down} rows, \"row\": {sinst[1]['_row'] + rows_down} at "
                           f"{sinst[0]}, or put {t['type']} on it as its \"label\"")
                else:
                    fix = (f"put {t['type']} in a band (\"band\": \"status\", \"title\" or \"hint\"), \"above\"/\"below\" "
                           f"{s['type']}, or on it as its \"label\"")
                problems.append(f"{tpath[0]}: the text {t['type']} {box_text(tb)} lies over {s['type']} {box_text(sb)}; {fix}")
        if primary:
            backdrop = next((ly["backgroundColor"] for ly in lay["layers"] if not ly["isTransparent"]), None)
            back = tuple(round(c * 255) for c in backdrop[:3]) if backdrop else gen.rgb("canvas")
            weight: dict[str, float] = {}
            for inst, b, is_text, hud in boxes:
                o = byname.get(inst["type"])
                if is_text or hud or not o or o["plugin"] != "Sprite":
                    continue
                fill = gen.rgb(o["_frames"][inst["properties"].get("initial-frame", 0)])
                area = (o["_size"][0] * U) * (o["_size"][1] * U)
                # one instance against one: three targets do not outweigh the player because there are three
                weight[o["name"]] = max(weight.get(o["name"], 0), area * gen.contrast(fill, back))
            if primary in weight:
                top = max(weight, key=weight.get)
                if top != primary and weight[top] > weight[primary]:
                    grow = math.sqrt(weight[top] / weight[primary]) * 1.1
                    p = byname[primary]
                    size = [min(SIZE_MAX, math.ceil(p["_size"][0] * grow)), min(SIZE_MAX, math.ceil(p["_size"][1] * grow))]
                    calmer = [r for r in gen.PALETTE if gen.contrast(gen.PALETTE[r], back) < 2]
                    problems.append(f"layout {lname}: spec.primary is {primary}, and {top} stands out more (its area "
                                    f"times its contrast with the background is {weight[top] / weight[primary]:.1f} times "
                                    f"{primary}'s); set spec.objects[{p['_i']}].size {size}, or draw {top} smaller or in "
                                    f"a role nearer the background ({', '.join(calmer) or 'none'})")
    for oname, path in tapped.items():
        o = byname[oname]
        if o["plugin"] != "Sprite" or any(inst.get("over") or inst.get("repeat", [1, 1]) != [1, 1]
                                          for lay in layouts_in for inst in lay.get("instances") or []
                                          if isinstance(inst, dict) and inst.get("object") == oname):
            continue
        least = math.ceil(gen.TOUCH / U)
        if min(o["_size"]) < least:
            problems.append(f"spec.objects[{o['_i']}].size: {oname} is tapped ({path}), and {o['_size'][0]} x "
                            f"{o['_size'][1]} units is smaller than a finger; set \"size\" "
                            f"[{max(least, o['_size'][0])}, {max(least, o['_size'][1])}]")
    if problems:
        raise Refused(f"{len(problems)} layout problem{'s' if len(problems) > 1 else ''}; fix them all, then build again:\n"
                      + "\n".join(f"{n}. {p}" for n, p in enumerate(problems, 1)))

    # Objects the events create need an instance to copy: one in a layout that never runs.
    unplaced = [n for n, o in byname.items() if o["plugin"] in ("Sprite", "Text") and n not in placed]
    if unplaced:
        objects_layout = gen.layout("Objects", [gen.layer("Objects")], None, (), vw, vh)
        for n in unplaced:
            o = byname[n]
            ivars = dict(o.get("variables") or {})
            behaviors = {b: {"properties": props} for b, props in o["_behaviors"]}
            objects_layout["layers"][0]["instances"].append(
                gen.shape_inst(n, files[n][0], 1, 1, ivars=ivars, behaviors=behaviors) if o["plugin"] == "Sprite"
                else gen.text_inst(n, "", U, U, 8 * U, 2 * U, ivars=ivars, behaviors=behaviors))
        layouts["Objects"] = objects_layout

    # --- write ---------------------------------------------------------------------------------
    for oname, t in types.items():
        gen.write_json(f"objectTypes/{oname}.json", t)
    for lname, lay in layouts.items():
        gen.write_json(f"layouts/{lname}.json", lay)
    for sh in sheets_in:
        gen.write_json(f"eventSheets/{sh['name']}.json", {"name": sh["name"], "events": [], "sid": gen.sid()})
    c3proj = out / "project.c3proj"
    existing = json.loads(c3proj.read_text(encoding="utf-8-sig"))
    p = gen.build_project(existing, types, {}, [], layouts, sheet_names)
    p["name"] = name.strip()
    p["uniqueId"] = "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
    p["firstLayout"] = layouts_in[0]["name"]
    p["properties"]["orientations"] = "portrait" if vh > vw else "landscape"
    gen.write_json("project.c3proj", p)
    n_inst = sum(len(ly["instances"]) for lay in layouts.values() for ly in lay["layers"])
    return [f"built: {len(types)} object types, {len(layouts)} layouts ({', '.join(layouts)}), {n_inst} instances, "
            f"viewport {vw}x{vh}, grid unit {U} px, theme {theme}"] + [f"note: {n}" for n in notes]


def run(script: str, args: list[str], rag: Path, locale: str, limit: int = 6000) -> tuple[int, str]:
    args = list(args)
    project = None
    if "--project" in args:
        at = args.index("--project")
        project = Path(args[at + 1])
        del args[at:at + 2]
    proc = copilot.run_script(script, args, project, locale=locale, limit=limit, timeout=STEP_TIMEOUT, rag=rag)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def in_a_row(ev: dict, where: str, arrays: dict[str, tuple[int, int]]) -> dict:
    """{"eventType": "n-in-a-row", "array": "Board", "count": 5, "value": "turn", "actions": [...]} as the block it
    stands for: loops "rowx" and "rowy" over the Array and one Compare two values that holds when `count` cells in a
    row, across, down or on either diagonal from (rowx, rowy), all equal `value`. Array.At outside the array is 0, so
    a line that runs off the edge fails without a bounds test, as long as `value` is never 0."""
    known = {"eventType", "array", "count", "value", "actions", "children"}
    extra = sorted(set(ev) - known)
    if extra:
        refuse(where, f"unknown key(s) {', '.join(map(repr, extra))}; n-in-a-row has {', '.join(sorted(known))}")
    name = ev.get("array")
    if name not in arrays:
        refuse(f"{where}.array", f"{name!r}; the Arrays of spec.objects are {', '.join(arrays) or 'none'}")
    w, h = arrays[name]
    n = whole(ev.get("count"), f"{where}.count", 2, max(w, h))
    if not ev.get("actions") and not ev.get("children"):
        refuse(f"{where}.actions", "empty, so a line found does nothing; put the actions that end the game here, "
                                   'e.g. Set state to 1')
    value = ev.get("value")
    if not isinstance(value, str) or not value.strip() or value.strip() == "0":
        refuse(f"{where}.value", 'the expression a cell of the line holds, never 0, the empty cell: "turn"')
    x, y = 'loopindex("rowx")', 'loopindex("rowy")'

    def cell(dx: int, dy: int, k: int) -> str:
        cx = f"{x} + {dx * k}" if dx * k > 0 else (f"{x} - {-dx * k}" if dx * k < 0 else x)
        cy = f"{y} + {dy * k}" if dy * k > 0 else (f"{y} - {-dy * k}" if dy * k < 0 else y)
        return f"({name}.At({cx}, {cy}) = {value})"

    test = " | ".join("(" + " & ".join(cell(dx, dy, k) for k in range(n)) + ")"
                      for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)))
    block = {"eventType": "block", "conditions": [
        {"id": "for", "objectClass": "System", "parameters": {"name": '"rowx"', "start-index": "0", "end-index": str(w - 1)}},
        {"id": "for", "objectClass": "System", "parameters": {"name": '"rowy"', "start-index": "0", "end-index": str(h - 1)}},
        {"id": "compare-two-values", "objectClass": "System",
         "parameters": {"first-value": test, "comparison": 0, "second-value": "1"}}],
        "actions": ev.get("actions") or []}
    if ev.get("children"):
        block["children"] = ev["children"]
    return block


def expand(events, where: str, arrays: dict[str, tuple[int, int]]):
    """The spec's own event kinds replaced by the events they stand for, at any depth."""
    if not isinstance(events, list):
        return events
    out = []
    for i, ev in enumerate(events):
        at = f"{where}[{i}]"
        if isinstance(ev, dict) and ev.get("eventType") == "n-in-a-row":
            ev = in_a_row(ev, at, arrays)
        if isinstance(ev, dict) and isinstance(ev.get("children"), list):
            ev = {**ev, "children": expand(ev["children"], f"{at}.children", arrays)}
        out.append(ev)
    return out


SELF_CHANGE = ("add-to-eventvar", "subtract-from-eventvar", "toggle-boolean-eventvar")


def every_tick(events, where: str, triggered: bool = False, above: str = "") -> None:
    """Refuse an event that runs every tick and changes a global from its own value: no trigger in it or above it,
    no Trigger once, so "turn = 3 - turn" or "Add 1 to score" runs sixty times a second. Such an event is meant
    as a sub-event of the event whose trigger it follows (a tap, On start of layout, a timer). An event whose
    actions change what its conditions, or those above it, read ends itself: a fruit that reaches the floor scores
    and is moved back up, so the score goes up once (a catch game, 2026-10-04)."""
    for i, ev in enumerate(events if isinstance(events, list) else []):
        if not isinstance(ev, dict) or ev.get("eventType") not in ("block", "group", None):
            continue
        at = f"{where}[{i}]"
        conds = [c for c in ev.get("conditions") or [] if isinstance(c, dict)]
        # Every X seconds paces itself like a trigger (check_project's PACING); refusing it sent a combo reset to a
        # Timer that stopped for good (2026-10-09)
        fires = triggered or any(str(c.get("id", "")).startswith("on-") or c.get("id") in ("trigger-once-while-true",
                                                                                         "every-x-seconds")
                                 for c in conds)
        for kind in ("conditions", "actions"):
            for k, ace in enumerate(ev.get(kind) or []):
                for key, value in ((ace.get("parameters") or {}).items() if isinstance(ace, dict) else ()):
                    if value == "":
                        # the checker lets it through and the editor refuses the project: "Empty expression"
                        refuse(f"{at}.{kind}[{k}].parameters.{key}", 'empty; the editor refuses an empty parameter. '
                               'Empty text is written "\\"\\"" (two quotes inside the string), a number "0"')
        blocks = [e for e in events if isinstance(e, dict) and e.get("eventType", "block") == "block"]
        if (ev.get("eventType", "block") == "block" and not conds and ev.get("actions") and len(blocks) > 1
                and any(b.get("conditions") for b in blocks if b is not ev) and blocks.index(ev) > 0):
            refuse(f"{at}.conditions", "empty, so it runs every time, beside siblings that test a case; if it is "
                   'the "otherwise" case, its one condition is {"id": "else", "objectClass": "System"}')
        read = above + json.dumps(conds)
        acts = [a for a in ev.get("actions") or [] if isinstance(a, dict)]
        changed = {str((a.get("parameters") or {}).get("variable", "")) for a in acts if a.get("objectClass") == "System"}
        changed |= {str(a.get("objectClass", "")) for a in acts if a.get("objectClass") != "System"}
        ends_itself = any(n and re.search(rf"(?<![\w.]){re.escape(n)}(?!\w)", read) for n in changed)
        if not fires and not ends_itself and ev.get("eventType") != "group":
            for k, a in enumerate(ev.get("actions") or []):
                if not isinstance(a, dict) or a.get("objectClass") != "System":
                    continue
                params = a.get("parameters") or {}
                name = str(params.get("variable", ""))
                if name and (a.get("id") in SELF_CHANGE or (a.get("id") == "set-eventvar-value" and re.search(
                        rf"(?<![\w.]){re.escape(name)}(?![\w(])", str(params.get("value", ""))))):
                    refuse(f"{at}.actions[{k}]", f"this event has no trigger, in it or above it, so it runs every tick "
                           f"and changes {name} from its own value sixty times a second. Make it a sub-event, under "
                           f"\"children\", of the event whose trigger it follows (the tap that places a piece, On start "
                           f"of layout, a timer), or start its conditions with that trigger. A tick rule of the design (a "
                           f"fruit reaching the floor) tests the object its actions move, Fruit.Y >= 1100 with an action "
                           f"that puts the Fruit back up, so the event stops itself")
        every_tick(ev.get("children"), f"{at}.children", fires, read)


def operations(events: list) -> tuple[list[dict], list[tuple[int, int]]]:
    """One edit_sheet operation per top-level event with the comments above it, which the plan needs in the same
    operation; and the spec indices each operation holds."""
    ops, spans, start = [], [], 0
    for i, ev in enumerate(events):
        if isinstance(ev, dict) and ev.get("eventType") == "comment" and i + 1 < len(events):
            continue
        ops.append({"into": 0, "events": events[start:i + 1]})
        spans.append((start, i))
        start = i + 1
    return ops, spans


def add_events(spec: dict, out: Path, rag: Path, locale: str) -> list[str]:
    said = []
    for s, sh in enumerate(spec.get("sheets") or []):
        arrays = {o["name"]: tuple(o.get("size", [10, 1])) for o in spec.get("objects") or []
                  if isinstance(o, dict) and o.get("plugin") == "Array"}
        events = expand(sh.get("events") or [], f"spec.sheets[{s}].events", arrays)
        every_tick(events, f"spec.sheets[{s}].events")
        if not events:
            continue
        ops, spans = operations(events)
        with copilot.temporary_directory() as tmp:
            plan = Path(tmp) / "plan.json"
            plan.write_text(json.dumps(ops, ensure_ascii=False), encoding="utf-8")
            code, text = run("edit_sheet", [sh["name"], str(plan), "--project", str(out)], rag, locale, limit=8000)

        def where(m: re.Match) -> str:
            a, b = spans[int(m.group(1)) - 1]
            return f"spec.sheets[{s}].events[{a}]" + (f"..[{b}]" if b > a else "")

        text = re.sub(r"\boperation (\d+)\b", lambda m: where(m) if int(m.group(1)) <= len(spans) else m.group(0), text)
        text = re.sub(r"\nnote: if the project is open in the Construct 3 editor[^\n]*", "", text)
        text = re.sub(r"(nothing was written|nothing written)", "nothing was built", text)
        if code != 0:
            raise Refused(text + f"\n-- fix the spec where the lines above say and build again. A line names the "
                                 f"place in sheet {sh['name']!r} by its event number too, as print_sheet numbers it")
        said += [line for line in text.splitlines() if line.startswith("warning:")]
        said.append(run("print_sheet", [sh["name"], "--project", str(out)], rag, locale, limit=4000)[1])
    return said


def main() -> int:
    ap = argparse.ArgumentParser(description="build a Construct 3 folder project from a JSON spec")
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="the project folder; replaced only when the build passes")
    ap.add_argument("--rag", type=Path, default=DEFAULT_RAG)
    ap.add_argument("--locale", default="zh-CN")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    template = args.rag / "data" / "c3-new-project"
    if not (template / "project.c3proj").is_file():
        print(f"the RAG clone has no empty project at {template}")
        return 2
    text = args.spec.read_text(encoding="utf-8-sig")
    fixed: list[str] = []
    try:
        if len(text) > SPEC_MAX:
            raise Refused(f"spec: {len(text)} characters, more than {SPEC_MAX}; make the game smaller")
        try:
            spec = json.loads(text)
        except json.JSONDecodeError as e:
            raise Refused(f"spec: not valid JSON, line {e.lineno} column {e.colno}: {e.msg}") from None
        if bool(copilot.OPTIONS.get("quick")):
            spec, fixed = quick_fix.tidy(spec)
        with copilot.temporary_directory() as tmp:
            work = Path(tmp) / "project"
            shutil.copytree(template, work, ignore=shutil.ignore_patterns(".git", "llm-context.md"))
            for stale in ("layouts/Layout 1.json", "eventSheets/Event sheet 1.json"):
                (work / stale).unlink(missing_ok=True)
            said = [f"fixed: {line}" for line in fixed] + build(spec, work, args.rag)
            said += add_events(spec, work, args.rag, args.locale)
            code, checked = run("check_project", ["--project", str(work)], args.rag, args.locale)
            if code != 0:
                raise Refused(checked + "\n-- the checker refused the built project; nothing was built. Fix the spec "
                                        "where its lines say: an object, layout or sheet named there is the spec's")
            # the checker's warnings reach the model: a text at the screen edge, a bullet never removed (2026-10-09)
            said += [line for line in checked.splitlines() if line.startswith("warning:") and line not in said]
            checked = re.sub(r"; next, review the design.*", "", checked.splitlines()[-1])
            if args.out.exists():
                shutil.rmtree(args.out)
            shutil.copytree(work, args.out)
    except Refused as e:
        print(f"refused, nothing was built:\n{e}" + "".join(f"\nfixed already: {line}" for line in fixed))
        return 1
    except (FileNotFoundError, ImportError) as e:
        print(f"the generator template could not be loaded: {e}")
        return 2
    print("\n".join(said + [checked, f"project folder: {args.out}"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
