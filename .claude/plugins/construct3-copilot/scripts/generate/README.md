# generate/ — Resource Generation Scripts

Generates Construct 3 assets: placeholder images, layout presets, clipboard JSON.
Always run `query/rag.py` to confirm ACE IDs before generating.

---

## imagedata.py — Placeholder Image Generation

Produces base64 PNG for object-types and world-instances imageData fields.

**When to use**: Need imageData for Sprite/TiledBg; user requests visual placeholders.
**When NOT to use**: User already has image files; generating events only (no object definitions).

```bash
python3 scripts/generate/imagedata.py --color red --width 32 --height 32
python3 scripts/generate/imagedata.py --kenney player --color blue
```

Output: base64 string, embed directly in clipboard JSON `imageData` array.

---

## layout.py — Layout Preset Generation

Generates complete layout clipboard JSON (layers, instances, object type definitions).

**When to use**: User requests a full layout (platformer, breakout, etc.); need objects + instances + layers together.
**When NOT to use**: User only needs an event sheet; modifying part of an existing layout.

```bash
python3 scripts/generate/layout.py --preset platformer -W 640 -H 480
python3 scripts/generate/layout.py --preset breakout -W 640 -H 480 -o out.json
```

Available presets: `platformer`, `breakout`. Output includes object-types + imageData.

---

## clipboard.py — Intent IR to C3 JSON [not ready]

Converts structured intent into paste-ready C3 clipboard JSON. Currently returns skeleton only.

**When to use**: Have a complete Intent IR that needs conversion to clipboard JSON.
**When NOT to use**: Current version — produces empty skeleton only.

```bash
echo '{"gameplay":["WASD movement"],"assets":["Player"]}' | python3 scripts/generate/clipboard.py
```

---

## Generation Workflow (mandatory order)

1. `query/rag.py` — confirm all ACE IDs exist
2. `generate/imagedata.py` — produce placeholder images (if object-types needed)
3. `generate/layout.py` or direct JSON authoring
4. `clipboard_service.py validate` — validate output; fix and re-validate on failure

## Anti-patterns

- Writing ACE conditions/actions into JSON without schema confirmation
- Generating layouts without imageData (Sprite paste will silently fail)
- Producing placeholder images without telling the user they are placeholders
