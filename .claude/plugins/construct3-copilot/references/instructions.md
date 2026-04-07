# Construct 3 Copilot — Workflow Guide

Load this file for detailed execution steps. Constraints and validation rules live in @CLAUDE.md. Script paths and reference routing live in @SKILL.md. Do not duplicate them here.

---

## 1. Intent IR Parsing

Parse user requests into structured intent:

```json
{
  "gameplay": ["player movement", "collision damage"],
  "ui": ["score text"],
  "assets": ["Player", "Enemy", "ScoreText"],
  "open_questions": ["Scoring rules?", "Win/lose conditions?"],
  "assumptions": []
}
```

- Populate each array with concise strings
- Include every ambiguity in `open_questions` — err on the side of asking
- `assets` must list every object/behavior the output will reference

## 2. Clarification Loop

When `open_questions` is non-empty:

1. Ask one question at a time using templates from @references/prompts.md
2. Wait for answer before proceeding
3. Record unavoidable assumptions in `assumptions` and state them in the final response

Stop clarifying when: all arrays are populated with concrete values and no ambiguous terms remain.

## 3. Session Memory

Track across turns in a short bullet list:
- Created objects and their behaviors
- Defined variables (name, type, initial value)
- Current layout name and layers
- Assumptions from prior turns

On incremental edits: consult and update this list. Reuse existing resources — do not rebuild from scratch.

## 4. Generation Pipeline

1. **Plan outputs** — Choose clipboard `type` per the table below. Present the plan for confirmation before emitting large payloads (>50 events).
2. **Schema retrieval** — Confirm every ACE ID via `scripts/query/schema.py`. When RAG is online, also run `scripts/query/rag.py search` for semantic context.
3. **Modular design** — Organize logic into groups: Input, Movement, Collision, Scoring, UI, Reset. Use `eventType: "group"` blocks.
4. **Author JSON** — Follow @references/clipboard-format.md. Use behavior display names (run `schema.py behavior {name}` to confirm).
5. **Validate** — Run `scripts/validate/output.py`. Fix and re-validate on failure (max 3 retries).

## 5. Output Types

| Type | Paste Location | Use When |
|------|----------------|----------|
| `events` | Event sheet margin | Movement/AI/collision/scoring logic |
| `object-types` | Project Bar → Object types | New sprites, globals, UI, singletons |
| `world-instances` | Layout view | Placing objects with positions |
| `layouts` | Project Bar → Layouts | Complete level (layers + instances + event sheet ref) |
| `event-sheets` | Project Bar → Event sheets | Entire sheet replacement |
| `conditions` / `actions` | Inline in Event Editor | Partial snippets |

## 6. Output Format

Every delivery must include:

```
1. JSON code block (validated, complete clipboard payload)
2. Paste location: "{exact location in C3 editor}"
3. Verify: "{what to check after pasting — e.g., run layout, confirm score updates}"
4. Assumptions: [list any assumptions made]
```

## 7. Language-Aware Presentation

Match the user's language when presenting ACE information:

- **Chinese conversation**: Use Chinese ACE names (from `schema.py` bilingual output) in explanations. Example: `键盘 > 按住按键 > 空格` not `Keyboard > Key is down > Space`.
- **English conversation**: Use English ACE names as-is.
- **Generated JSON**: Always English IDs regardless of conversation language.

## 8. Design Principles

### State Machines
- Enum variables for state: `GameState` (0=playing, 1=paused, 2=gameover)
- `Is*` prefix for booleans: `IsPaused`, `IsInvincible`

### Event Organization
- Group by responsibility: Input → Movement → Collision → Scoring → UI → Reset
- Lifecycle order: `On start` init → Runtime loops → End detection → Cleanup/restart
- Use `eventType: "group"` with clear titles

### Complete Loop Mandate
Every output provides a full playable loop: Controls → Core mechanics → Scoring → Win/lose → Restart. If user requests a fragment, either:
- Scope it explicitly ("this pastes into the Collision group only"), or
- Fill in missing scaffolding (variables, UI text, restart action)

### Coordinate System
Construct 3: top-left origin (0,0), +X right, +Y down. Double-check when emitting positions or comparisons.

### Naming
- Consistent names across variables/objects/behaviors
- Document custom rules (score multipliers, power-up states) in output comments

### TiledBackground
- Tile textures: 32x32 or 64x64, seamless
- Use repeat wrapping for infinite backgrounds
- Full-screen sprites only when a single stretched image is required
