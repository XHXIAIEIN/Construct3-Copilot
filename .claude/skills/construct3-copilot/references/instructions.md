# Construct 3 Copilot Instructions

This document contains the full workflow for generating Construct 3 clipboard payloads. Load only
what you need—metadata in `SKILL.md` is intentionally brief so Claude can decide whether to fetch
this file.

## 1. Purpose & Capabilities

- Generate **event sheets**, **object types**, **layouts/world instances**, and accompanying resource
  manifests (variables/assets/mapping) so results are paste-ready.
- Produce deterministic **imageData** and map it back into objects or layouts.
- Query ACE schemas and mined examples to keep every action/condition grounded in real usage.
- Maintain session memory so multi-turn edits reuse existing objects/variables.
- Validate and self-review output before responding.

## 2. Conversation Workflow

### 2.1 Intent Parsing (Intent IR)
1. Extract the user requirement into the JSON structure defined in
   [`intent_schema.json`](intent_schema.json). Example:
   ```json
   {
     "gameplay": ["player movement", "collision damage"],
     "ui": ["score text"],
     "assets": ["player sprite", "brick"],
     "open_questions": ["scoring amount?", "win/lose condition?"]
   }
   ```
2. Keep `open_questions` exhaustive. This IR drives all later steps.

### 2.2 Clarification Loop
- If `open_questions` is non-empty, ask follow-ups using the templates in `prompts.md`. Ask one at a
  time and wait for answers before producing JSON.
- If assumptions are unavoidable, state them explicitly in the final response.

### 2.3 Session Memory
- Track objects, variables, layouts, assets, and assumptions from prior turns in a short bullet list.
- When the user requests incremental changes, consult and update this memory instead of rebuilding
  everything.

## 3. Structured Generation Pipeline

1. **Plan outputs** – Choose appropriate clipboard `type` values (events, object-types, layouts,
   etc.) per Section 5 below.
2. **Schema/RAG retrieval** – Use `scripts/query_schema.py` to confirm ACE IDs/params. If
   `data/project_analysis` exists, run `scripts/query_examples.py` to pull real usage snippets for
   grounding.
3. **Modular design** – Organize logic into groups (player control, spawn, scoring, UI...). Emit
   `eventType: "group"` blocks or return grouped JSON (`groups`, `variables`, `objects`, `events`).
4. **Resource manifests** – Compile variables/assets/mapping sections describing every referenced
   symbol. Pair each event/output with the manifest entries.
5. **Author JSON** – Follow `references/clipboard-format.md`. Respect behavior display names (see
   `behavior-names.md`) and parameter rules (string quotes, numeric comparisons, etc.).
6. **Self-review** – Run through the checklist in `checklist.json`. Fix issues before replying.
7. **Validation & testing** – Execute `scripts/validate_output.py '<json>'`. Suggest at least one
   verification step (e.g., "After pasting, run the test layout and confirm ScoreText updates").

## 4. Clarification & Iteration Prompts

- Use the templates in `prompts.md`:
  - **Intent extraction** prompt
  - **Clarification** prompt ("Should each hit award +1 point, or do you need score multipliers?")
  - **Generation** prompt (outline groups/resources before emitting JSON)
  - **Self-review** prompt (run through the checklist)
- Always present the planned groups/resources for confirmation before emitting large payloads.
- Offer incremental patches (diffs) when users request edits.

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
  - `python3 scripts/generate_imagedata.py --color red --width 32 --height 32`
  - `python3 scripts/generate_imagedata.py --kenney player --color blue`
  - `python3 scripts/generate_imagedata.py --file sprite.png`
- **Layout presets** (`scripts/generate_layout.py`)
  - `python3 scripts/generate_layout.py --preset platformer -W 640 -H 480 -o layout.json`
  - `python3 scripts/generate_layout.py --preset breakout -W 640 -H 480 -o layout.json`
- **Schema lookup** (`scripts/query_schema.py`)
  - `python3 scripts/query_schema.py plugin sprite set-animation`
  - `python3 scripts/query_schema.py behavior platform simulate-control`
- **Example mining** (`scripts/query_examples.py`)
  - Use only if `data/project_analysis/*.json` exists.
  - `python3 scripts/query_examples.py action create-object`
  - `python3 scripts/query_examples.py top actions 20`
- **Validation** (`scripts/validate_output.py`)
  - `python3 scripts/validate_output.py '<json>'` (accepts stdin or file path).

## 7. References

| Resource | Purpose |
|----------|---------|
| `references/clipboard-format.md` | JSON structures, parameter rules, clipboard write instructions, script actions |
| `references/runtime-api.md` | JavaScript/TypeScript scripting API (IRuntime, IInstance, etc.) |
| `source/scripts/ts-defs/` | Complete TypeScript type definitions |
| `references/object-templates.md` | Sprite/UI/global templates with imageData |
| `references/layout-templates.md` | Layout/world instance templates |
| `references/behavior-names.md` | behaviorId → behaviorType mapping |
| `references/zh-cn.md` | Localized terminology/search tips |
| `references/addon-sdk-index.md` | Plugin/Behavior development quick reference |
| `references/addon-sdk/guide/` | Addon SDK development guides |
| `references/addon-sdk/reference/` | Addon SDK API reference |
| `references/troubleshooting.md` | Paste errors, ACE issues, parameter mismatches |
| `references/deprecated-features.md` | Modern replacements for Function/Pin/Fade |
| `references/prompts.md` | Intent extraction, clarification, generation, review templates |
| `references/intent_schema.json` | Formal Intent IR structure |
| `references/checklist.json` | Validation/self-review rules |
| `references/examples.md` | End-to-end request → output samples |

## 8. Scope & Limitations

- Only generates Construct 3 clipboard JSON (events, object-types, layouts, world-instances,
  event-sheets, conditions, actions). Does **not** generate project files or code for other engines.
- Requires that target objects/behaviors exist or are defined in the same output; does not interface
  with runtime APIs beyond Construct 3 clipboard paste.
- Graphics output is limited to deterministic PNG imageData via `scripts/generate_imagedata.py`; this
  skill does not call external diffusion/AI art models.
- Validation script must pass before delivery. If structural errors persist, block output and ask for
  corrections instead of guessing.

## 9. Examples

See `references/examples.md` for canonical input/Intent IR/output combinations. Use them as
groundtruth when the user request resembles those scenarios.

## 10. Construct 3 Design Guidelines

- **State machine naming** – Use numeric enums such as `GameState`, `EnemyState` with inline comments
  (`0=playing,1=gameover`). Reserve `Is*` prefixes for boolean flags (`IsPaused`, `IsInvincible`) and
  keep their values strictly true/false or 0/1.
- **Separate logic from presentation** – Logic events manipulate variables/behaviors only; UI updates
  (text, animations) live in dedicated groups. When listing resources, keep manifests for data objects
  separate from visual assets so they can be swapped independently.
- **Visual style spec** – Always ask for or infer a style brief (palette, resolution, shape language).
  When using `scripts/generate_imagedata.py`, set color/shape parameters to match that brief instead
  of defaulting to flat retro squares. Document the style in the resource manifest so future assets
  stay coherent.
- **Coordinate discipline** – Construct layouts use a top-left origin (0,0) with +X to the right and
  +Y down. When emitting world instances or comparing positions, double-check you are not assuming a
  bottom-left origin; align brick grids and camera clamps using this convention and the objects’
  actual origins.
- **End-of-game settlement** – Dedicate a group that freezes gameplay state (`GameState` enum, disable
  controls), surfaces summary UI (“Score”, remaining lives, clear reason), and exposes the restart
  input. Avoid leaving only partial actions (e.g., destroying the ball without updating the UI); the
  manifest should describe which text objects display the final totals.
- **Complete loop mandate** – Before responding, make sure every output provides a full playable
  loop: controls → core mechanics → scoring/progression → lose/win handling → restart or next-step
  hook. If the user only asked for a snippet, either scope it explicitly (“this pastes into the
  Collision group only”) or fill in the missing scaffolding (variables, UI text, restart action) so
  the user can immediately run the result.
- **Lifecycle coverage** – Structure the event groups so they read like a lifecycle: `On start`
  initialization (variables, HUD, object spawns) → runtime loops (input, AI, timers) → failure/win
  detection → cleanup/restart. If any stage is intentionally omitted, clearly label the gap and avoid
  referencing undeclared state from the missing stages.
- **TiledBackground discipline** – Keep tile textures small and seamless (e.g., 32x32 or 64x64). Use
  repeat wrapping for infinite backgrounds; only use full-screen sprites when a single stretched
  image is required.
- **Layered event organization** – Group events by responsibility (input, movement, collisions, UI,
  reset, etc.) using `eventType: "group"` and clear comments. Never dump unrelated events into the
  same group.
- **Preferred patterns**:
  - Model multi-step flows with enum state machines instead of multiple loosely coupled booleans.
  - Favor data-driven layouts (arrays/dictionaries describing bricks/enemies) and loops over
    hard-coded duplicates.
  - Route gameplay → UI interactions through variables or messages rather than directly referencing
    UI details everywhere.
- **Naming consistency** – Use consistent naming across variables/objects/behaviors. If custom rules
  are needed (e.g., score multipliers, power-up states), document them inside the manifest or inline
  comments so follow-up actions can reason about them.
