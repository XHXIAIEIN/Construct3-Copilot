name: construct3-copilot
description: >
  Generates Construct 3 clipboard JSON (events, object-types, layouts, imageData) for paste-ready
  workflows. Trigger whenever a request mentions Construct 3/C3 event sheets, behaviors, objects,
  layouts, clipboard JSON, schema-mapped actions, or validation of generated logic.
triggers:
  keywords:
    - construct 3
    - c3
    - event sheet
    - clipboard json
    - layout
    - behavior
    - object type
  intents:
    - generate_construct3_events
    - generate_construct3_layout
    - validate_construct3_logic
---

# Construct 3 Copilot

Minimal metadata keeps context small. Load the referenced files when executing the skill.

## Quick Start (Claude-facing)

1. Parse the user request into the Intent IR defined in
   [`references/intent_schema.json`](references/intent_schema.json).
2. Use clarification templates from [`references/prompts.md`](references/prompts.md) if
   `open_questions` remains.
3. Follow the full workflow in [`references/instructions.md`](references/instructions.md) covering
   planning, modular generation, resource manifests, validation, and delivery.
4. Before responding, run the checklist in [`references/checklist.json`](references/checklist.json)
   and execute `scripts/validate_output.py`.

## Script Inventory

| Script | Purpose |
|--------|---------|
| `scripts/generate_imagedata.py` | Deterministic PNG base64 generation |
| `scripts/generate_layout.py` | Layout presets (platformer, breakout, etc.) |
| `scripts/query_schema.py` | ACE schema lookup |
| `scripts/query_examples.py` | Mine usage stats/examples (requires `data/project_analysis`) |
| `scripts/validate_output.py` | Clipboard JSON validation |

## Reference Map

| Resource | Description |
|----------|-------------|
| `references/instructions.md` | Full workflow + automation details |
| `references/prompts.md` | Intent, clarification, generation, self-review templates |
| `references/intent_schema.json` | Intent IR schema |
| `references/checklist.json` | Validation rules |
| `references/clipboard-format.md` | Clipboard format + parameter rules |
| `references/object-templates.md` | Object templates + imageData |
| `references/layout-templates.md` | Layout/world-instance templates |
| `references/behavior-names.md` | behaviorId ↔ behaviorType mapping |
| `references/zh-cn.md` | Localized terminology/search hints |
| `references/troubleshooting.md` | Error mitigation steps |
| `references/deprecated-features.md` | Modern replacements for legacy features |
