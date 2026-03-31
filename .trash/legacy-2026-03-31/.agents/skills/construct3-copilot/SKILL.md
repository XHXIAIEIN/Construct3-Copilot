---
name: construct3-copilot
description: >
  Generate Construct 3 clipboard JSON for event sheets, object types, layouts,
  and world instances with strict ACE-schema lookup and validation. Use when
  requests mention Construct 3/C3, event sheets, clipboard JSON, gameplay logic,
  controls, collision, scoring, UI, level/layout design, plugin or behavior ACE,
  or Chinese equivalents such as 事件表、布局、精灵、行为.
---

# Execute Workflow

## 1. Load required constraints first

- Read `@CLAUDE.md` before generating any output.
- Read `@references/instructions.md` for command usage details.
- Read `@references/clipboard-format.md` before outputting JSON.

## 2. Parse request into Intent IR

- Use schema from `@references/intent_schema.json`.
- Capture: gameplay, UI, assets, visual style, open questions, assumptions.
- Ask clarification questions when open questions are not empty.
- Ask one question at a time and wait for user response.

## 3. Run mandatory ACE lookup sequence

Never guess ACE IDs or parameter keys from memory.

```bash
python .agents/skills/construct3-copilot/scripts/query_schema.py search {keyword}
python .agents/skills/construct3-copilot/scripts/query_schema.py plugin {name} {ace}
python .agents/skills/construct3-copilot/scripts/query_schema.py behavior {name} {ace}
python .agents/skills/construct3-copilot/scripts/query_examples.py action {ace_id}
python .agents/skills/construct3-copilot/scripts/query_examples.py condition {ace_id}
```

Use only ACE IDs confirmed by lookup output.

## 4. Build output from validated templates

Load only needed references:

- Object scaffolds: `@references/object-templates.md`
- Layout scaffolds: `@references/layout-templates.md`
- Family patterns: `@references/family-patterns.md`
- Runtime script blocks: `@references/runtime-api.md`
- Behavior display-name mapping: `@references/behavior-names.md`
- Effect usage: `@references/effects-guide.md`
- Known unsupported/deprecated items: `@references/deprecated-features.md`
- Troubleshooting: `@references/troubleshooting.md`
- Recovery and regression loop: `@references/recovery-and-regression.md`
- Chinese terminology mapping: `@references/zh-cn.md`

For Addon SDK tasks:

- Entry map: `@references/addon-sdk-index.md`
- Guides: `@references/addon-sdk/guide/`
- API reference: `@references/addon-sdk/reference/`

## 5. Validate before final response

```bash
python .agents/skills/construct3-copilot/scripts/validate_output.py '<json>'
python scripts/preflight.py output.json
```

Fix validation errors before returning output.

# Output Contract

- Return Construct 3 clipboard JSON only (no `.c3p` project output).
- Include `"is-c3-clipboard-data": true`.
- Restrict `type` to: `events`, `conditions`, `actions`, `object-types`, `world-instances`, `layouts`, `event-sheets`.
- Use numeric operators for comparisons (`0..5`), not symbolic strings.
- Use numeric keycodes for keyboard parameters.
- Use nested quotes for string literal parameters (for example `"\"Hello\""`).
- For behavior ACE actions/conditions, include `behaviorType` display name.
- For variable events, include `comment`, `type`, and `initialValue`.

# Delivery Requirements

Every final answer must include:

- One JSON code block.
- Exact paste destination in Construct 3 editor.
- Manual verification checklist for the pasted result.
- Explicit assumptions list.

# Boundaries

- Generate placeholders only for art (`generate_imagedata.py`).
- Do not claim support for production art generation.
- Keep outputs Construct 3 specific.
