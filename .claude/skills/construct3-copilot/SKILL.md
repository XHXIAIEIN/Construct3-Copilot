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

- Generate **event sheets**, **object types**, **layouts/world instances**, and supporting resource
  manifests so the user can paste once and run.
- Produce valid **imageData** and reuse deterministic assets to avoid bloat.
- Query ACE schemas + historical examples to ground every action/condition.
- Maintain session memory (objects/variables defined so far) for multi-turn workflows.
- Validate/auto-review output before handing it to the user.

## 2. Conversation Workflow (Claude-facing)

### 2.1 Intent parsing (IR step)
1. Read the user request and emit an **Intent IR** before generating anything else:
   ```json
   {
     "gameplay": ["player movement", "collision damage"],
     "ui": ["score text"],
     "assets": ["player sprite", "brick"],
     "open_questions": ["scoring amount?", "win/lose condition?"]
   }
   ```
2. Use this structure to drive the rest of the workflow. Keep the IR concise but exhaustive.

### 2.2 Clarification loop
- If `open_questions` is non-empty or requirements conflict, ask the user targeted follow-ups.
- Example follow-up: "Should each hit award +1 point, or do you need score multipliers?"
- Do not proceed to generation until blocking questions are answered or assumptions are recorded and
  clearly communicated.

### 2.3 Session memory
- Track previously created objects, variables, layouts, and assumptions in a short bullet list.
- Reuse this memory when the user requests incremental changes (“加个暂停菜单”).
- Update the memory snapshot each time new resources are added.

## 3. Structured Generation Pipeline

1. **Plan outputs**
   - Use the table in Section 5 to decide which clipboard payloads are needed.
2. **Schema/RAG retrieval**
   - Use `scripts/query_schema.py` and, when `data/project_analysis` exists, `scripts/query_examples.py`
     to fetch usage patterns. Inject relevant snippets into the prompt before drafting events.
3. **Modular design**
   - Outline groups: player control, enemy AI, scoring, UI, etc.
   - Map each Intent IR item to a group so that resulting JSON is clustered, not flat.
4. **Resource manifests**
   - Assemble `variables.json`, `assets.json`, and `mapping.json` style summaries (can be embedded
     after the event payload). Ensure every referenced object/variable exists in the manifests.
5. **Author JSON**
   - Follow `references/clipboard-format.md`.
   - Ensure groups are emitted via `eventType: "group"` with children, or return a structured JSON
     object containing `groups`, `variables`, `objects`, `events`.
6. **Self-review**
   - Perform an explicit checklist review (Section 8) and fix issues before responding.
7. **Validation + test suggestions**
   - Run `scripts/validate_output.py`.
   - Suggest at least one verification step (e.g., "After pasting, run the test layout and confirm ScoreText updates").

## 4. Clarification & Iteration Prompts

- Opening clarifiers:
  - “需要键鼠还是触摸控制？”
  - “关卡结束条件是什么？”
- Iterative loop:
  - Present a concise summary of planned groups/resources, await confirmation, then emit JSON.
  - After delivery, offer to patch/extend existing events instead of regenerating from scratch.

## 5. Output Types

| Type | Paste Location | Use When |
|------|----------------|----------|
| `events` | Event sheet margin | Movement/AI/collision/scoring logic |
| `object-types` | Project Bar → Object types | New sprites, globals, UI, singletons |
| `world-instances` | Layout view | Placing objects with positions |
| `layouts` | Project Bar → Layouts | Complete level (layers + instances + event sheet reference) |
| `event-sheets` | Project Bar → Event sheets | Entire sheet replacement |
| `conditions` / `actions` | Inline in Event Editor | Partial snippets |

## 6. Automation & Tools

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

## 7. Reference Library (load on demand)

| File | When to read |
|------|--------------|
| [references/clipboard-format.md](references/clipboard-format.md) | Need JSON structures, parameter rules, clipboard write instructions |
| [references/object-templates.md](references/object-templates.md) | Creating sprites, UI objects, globals, behaviors, or singletons |
| [references/layout-templates.md](references/layout-templates.md) | Building full layouts/world instances |
| [references/behavior-names.md](references/behavior-names.md) | Converting `behaviorId` → `behaviorType` display names |
| [references/zh-cn.md](references/zh-cn.md) | Aligning Chinese terminology or searching localized schemas |
| [references/troubleshooting.md](references/troubleshooting.md) | Handling paste failures, ACE errors, or parameter mismatches |
| [references/deprecated-features.md](references/deprecated-features.md) | Replacing Function plugin/Pin/Fade usage with modern equivalents |

## 8. Quality Checklist

- [ ] Every JSON payload includes `"is-c3-clipboard-data": true`, correct `type`, and `items` array.
- [ ] Strings use nested quotes (`"\"Text\""`), comparisons use numeric operators (0–5), key codes are
      numeric.
- [ ] Behavior actions specify `behaviorType` using display names (see behavior-names reference).
- [ ] Variables include `comment`, `type`, and `initialValue`.
- [ ] Layout/object payloads reuse shared `imageData` indexes; image assets reference deterministic
      blobs from templates or generator.
- [ ] Validation script reports success; share warnings plus remediation with the user.
- [ ] Document paste instructions (event sheet margin, Project Bar path, etc.) in the final reply.
- [ ] Provide resource manifests (variables/assets) and mention any dependencies or tests to run.
- [ ] Confirm clarifications/assumptions in the response so the user can correct you.

## 9. Troubleshooting

- Paste errors → run validator + consult `references/troubleshooting.md`.
- Missing ACE → rerun `scripts/query_schema.py` or inspect schema JSON under `data/schemas`.
- Deprecated APIs → check `references/deprecated-features.md` and suggest modern constructs (Functions
  system, hierarchies, Tween).
- Image decoding issues → regenerate PNG via script; never embed ad-hoc base64 blobs without testing.
- Visual/style inconsistencies → request a style spec from the user (palette, resolution, animation
  states) before generating new assets.
