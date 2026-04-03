## Purpose

Minimal context for AI coding agents to be productive in this repository.

## What This Repo Does

Outputs are Construct 3 clipboard JSON (events, object-types, layouts). Paste into the C3 editor (Event sheet margin, Project Bar, Layout view).

## Read First

- `.claude/skills/construct3-copilot/SKILL.md` — execution workflow, helper scripts, hard boundaries
- `.claude/skills/construct3-copilot/CLAUDE.md` — strict generation constraints and hallucination traps
- `data/schemas/index.json` — canonical ACE schema index (plugins, behaviors, effects)

## Mandatory Workflow

```
QUERY → GENERATE → VALIDATE → FIX
```

1. Resolve every ACE ID via schema lookup before using it — never guess
2. Generate clipboard JSON following `references/clipboard-format.md`
3. Validate with `scripts/validate/output.py` — fail = do not deliver
4. Include paste location and manual verification step in every response

## Key Commands

```bash
# ACE schema lookup (MANDATORY)
python .claude/skills/construct3-copilot/scripts/query/schema.py search {keyword}
python .claude/skills/construct3-copilot/scripts/query/schema.py plugin {name} {ace}

# Validate generated JSON
python .claude/skills/construct3-copilot/scripts/validate/output.py '<json>'

# Generate placeholder art
python .claude/skills/construct3-copilot/scripts/generate/imagedata.py --color red --width 64 --height 64

# Regenerate ACE schema after CSV updates
node scripts/generate-schema.js source/zh-CN_R466.csv data/schemas/
```

## Conventions

- Do not invent ACE IDs — always query schema first
- Output clipboard JSON fragments only, not `.c3p` archives
- Run validation before returning any JSON
- Produce only Construct 3 output — no other engines

## Where to Look

- ACE schema: `data/schemas/`
- Skill references: `.claude/skills/construct3-copilot/references/`
- TypeScript definitions: `source/scripts/ts-defs/`
- Test fixtures: `tests/examples/`
