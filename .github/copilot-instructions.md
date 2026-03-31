## Purpose

This file gives AI coding agents minimal, actionable context to be productive in this repository.

## Quick context

- Outputs are Construct 3 clipboard JSON (events, object-types, layouts). Paste into the editor (Event sheet margin, Project Bar, Layout view).
- Primary automation and runtime data live under `data/schemas/` and `.agents/skills/construct3-copilot/`.
- `.claude/skills/construct3-copilot/` is kept for Claude compatibility.

## Essential files to read first

- [.agents/skills/construct3-copilot/SKILL.md](.agents/skills/construct3-copilot/SKILL.md) - execution workflow, helper scripts, hard boundaries.
- [.agents/skills/construct3-copilot/CLAUDE.md](.agents/skills/construct3-copilot/CLAUDE.md) - strict generation constraints and output conventions.
- [README.md](README.md) and [source/README.md](source/README.md) - project overview and schema workflow.
- [data/schemas/index.json](data/schemas/index.json) - canonical schema index (plugins, behaviors, effects).
- [tests/fixtures/events_basic.json](tests/fixtures/events_basic.json) - minimal valid JSON example.

## Project architecture (big picture)

- The `.agents` skill is the primary orchestrator for Codex.
- `data/schemas/` contains the generated ACE schema, produced from `source/zh-CN_R466.csv` via `scripts/generate-schema.js`.
- Skill scripts under `.agents/skills/construct3-copilot/scripts/` enforce lookup and validation workflows.

## Developer workflows (commands to run)

- Validate generated JSON before returning it to a user:

  python scripts/preflight.py output.json

- Query ACE schema (MANDATORY - do not guess ACE IDs):

  python .agents/skills/construct3-copilot/scripts/query_schema.py plugin {name} {ace}
  python .agents/skills/construct3-copilot/scripts/query_schema.py behavior {name} {ace}
  python .agents/skills/construct3-copilot/scripts/query_schema.py search {keyword}

- Lookup real-world examples (match engine usage):

  python .agents/skills/construct3-copilot/scripts/query_examples.py action {ace_id}
  python .agents/skills/construct3-copilot/scripts/query_examples.py condition {ace_id}

- Generate placeholders or layouts:

  python .agents/skills/construct3-copilot/scripts/generate_imagedata.py --color red --width 64 --height 64
  python .agents/skills/construct3-copilot/scripts/generate_layout.py --preset platformer -W 1280 -H 720

- Regenerate ACE schema after CSV updates:

  node scripts/generate-schema.js source/zh-CN_R466.csv data/schemas/

## Project-specific conventions and patterns

- Do not invent ACE IDs; always query schema files first.
- Output clipboard JSON fragments only, not `.c3p` archives.
- Use placeholder image generation for visuals.
- Run validation tooling (`validate_output.py` or `preflight.py`) before returning JSON.

## Integration points and examples

- ACE schema: [data/schemas/](data/schemas/) - resolve plugin/behavior/action/condition IDs here.
- Prompt and template references: `.agents/skills/construct3-copilot/references/`.
- Minimal fixture: [tests/fixtures/events_basic.json](tests/fixtures/events_basic.json).

## Short checklist for agents

- Read `SKILL.md` and `CLAUDE.md` first.
- Resolve ACE IDs via `query_schema.py`.
- Validate with `python scripts/preflight.py` or `validate_output.py`.
- Produce only clipboard JSON fragments and include exact paste steps.

## Where to look for more detail

- Type definitions and scripting: [source/README.md](source/README.md) and `scripts/ts-defs/`.
- Skill constraints and examples: `.agents/skills/construct3-copilot/references/`.
- Schema generation: [scripts/generate-schema.js](scripts/generate-schema.js).
