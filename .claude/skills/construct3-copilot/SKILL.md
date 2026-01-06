---
name: construct3-copilot
description: >
  Generates Construct 3 clipboard JSON (events, object-types, layouts, imageData) for paste-ready
  workflows. Trigger whenever a request mentions Construct 3/C3 event sheets, behaviors, objects,
  layouts, clipboard JSON, schema-mapped actions, or validation of generated logic.
---

# Construct 3 Copilot

Authoritative workflow for producing Construct 3 clipboard JSON that pastes cleanly into the editor.
Follow these instructions exactly; load additional references only when the step calls for them to
keep the context lean.

## 1. Purpose & Capabilities

- Generate **event sheets** (logic), **object types**, and **layouts/world instances**
- Produce valid **imageData** (PNG base64) for sprites/tiles and map them into objects/layouts
- Query ACE schemas to avoid hallucinated IDs or missing parameters
- Validate all clipboard payloads before presenting them to the user
- Provide localized ACE terms by referencing the zh-CN lexicon when necessary

## 2. Quick Start (default workflow)

1. **Capture the requirement**
   - Clarify whether the user needs events, objects, layouts, or a combination.
   - Confirm target object/behavior names and any custom variables.
2. **Plan the output type** using the table in Section 4.
3. **Map intents to ACEs**
   - Search schemas via `scripts/query_schema.py` or the RAG generator when uncertain.
   - Use `references/behavior-names.md` for correct `behaviorType` values.
4. **Author JSON** following the structures in `references/clipboard-format.md`.
5. **Validate**
   - Run `scripts/validate_output.py '<json>'`.
   - Resolve every error; surface warnings with remediation guidance.
6. **Deliver**
   - Explain where to paste (`events`, `object-types`, etc.).
   - Include any setup assumptions (objects already in project, required behaviors, etc.).

## 3. Core Workflow Details

1. **Intent triage**
   - Movement/AI/collision/score requests → events
   - Requests for sprites/UI assets → object-types
   - Full scenes/levels → layouts or world-instances
2. **Schema alignment**
   - Open `references/clipboard-format.md` for structural rules.
   - Use `scripts/query_schema.py plugin <name> <ace>` whenever ACE IDs/params are uncertain.
3. **Object/image pipeline**
   - Derive assets from `references/object-templates.md`.
   - Use `scripts/generate_imagedata.py` presets to keep imageData deterministic. Store reused
     assets in layouts rather than duplicating blobs.
4. **Layout construction**
   - Start from `references/layout-templates.md`; adjust layers, parallax, and event sheet mapping.
5. **Localization/terminology**
   - Use `references/zh-cn.md` when the requirement is written in Chinese to keep ACE terminology
     consistent with localized schema entries.
6. **Validation & packaging**
   - Always run `scripts/validate_output.py` and report success/failure.
   - For large payloads, suggest saving to file + clipboard instructions (Blob API snippet is in
     `references/clipboard-format.md`).

## 4. Output Types

| Type | Paste Location | Use When |
|------|----------------|----------|
| `events` | Event sheet margin | Movement/AI/collision/scoring logic |
| `object-types` | Project Bar → Object types | New sprites, globals, UI, singletons |
| `world-instances` | Layout view | Placing objects with positions |
| `layouts` | Project Bar → Layouts | Complete level (layers + instances + event sheet reference) |
| `event-sheets` | Project Bar → Event sheets | Entire sheet replacement |
| `conditions` / `actions` | Inline in Event Editor | Partial snippets |

## 5. Automation & Tools

- **ImageData generation** (`scripts/generate_imagedata.py`)
  - Solid shapes: `python3 scripts/generate_imagedata.py --color red --width 32 --height 32`
  - Kenney presets: `python3 scripts/generate_imagedata.py --kenney player --color blue`
  - Custom files: `python3 scripts/generate_imagedata.py --file sprite.png`
- **Layout presets** (`scripts/generate_layout.py`)
  - Platformer: `python3 scripts/generate_layout.py --preset platformer -W 640 -H 480 -o layout.json`
  - Breakout: `python3 scripts/generate_layout.py --preset breakout -W 640 -H 480 -o layout.json`
- **Schema lookup** (`scripts/query_schema.py`)
  - `python3 scripts/query_schema.py plugin sprite set-animation`
  - `python3 scripts/query_schema.py behavior platform simulate-control`
- **Example mining** (`scripts/query_examples.py`)
  - Use **only if** `data/project_analysis/*.json` exists (some repo checkouts omit these files).
  - `python3 scripts/query_examples.py action create-object`
  - `python3 scripts/query_examples.py top actions 20`
  - Returns real project snippets + common parameter values to ground prompts when designing novel
    logic.
- **Validation** (`scripts/validate_output.py`)
  - `python3 scripts/validate_output.py '<json>'`
  - Accepts stdin or file path; review warnings and fix root causes.

## 6. Reference Library (load on demand)

| File | When to read |
|------|--------------|
| [references/clipboard-format.md](references/clipboard-format.md) | Need JSON structures, parameter rules, clipboard write instructions |
| [references/object-templates.md](references/object-templates.md) | Creating sprites, UI objects, globals, behaviors, or singletons |
| [references/layout-templates.md](references/layout-templates.md) | Building full layouts/world instances |
| [references/behavior-names.md](references/behavior-names.md) | Converting `behaviorId` → `behaviorType` display names |
| [references/zh-cn.md](references/zh-cn.md) | Aligning Chinese terminology or searching localized schemas |
| [references/troubleshooting.md](references/troubleshooting.md) | Handling paste failures, ACE errors, or parameter mismatches |
| [references/deprecated-features.md](references/deprecated-features.md) | Replacing Function plugin/Pin/Fade usage with modern equivalents |

## 7. Quality Checklist

- [ ] Every JSON payload includes `"is-c3-clipboard-data": true`, correct `type`, and `items` array.
- [ ] Strings use nested quotes (`"\"Text\""`), comparisons use numeric operators (0–5), key codes are
      numeric.
- [ ] Behavior actions specify `behaviorType` using display names (see behavior-names reference).
- [ ] Variables include `comment`, `type`, and `initialValue`.
- [ ] Layout/object payloads reuse shared `imageData` indexes; image assets reference deterministic
      blobs from templates or generator.
- [ ] Validation script reports success; share warnings plus remediation with the user.
- [ ] Document paste instructions (event sheet margin, Project Bar path, etc.) in the final reply.

## 8. Troubleshooting

- Paste errors → run validator + consult `references/troubleshooting.md`.
- Missing ACE → rerun `scripts/query_schema.py` or inspect schema JSON under `data/schemas`.
- Deprecated APIs → check `references/deprecated-features.md` and suggest modern constructs (Functions
  system, hierarchies, Tween).
- Image decoding issues → regenerate PNG via script; never embed ad-hoc base64 blobs without testing.
