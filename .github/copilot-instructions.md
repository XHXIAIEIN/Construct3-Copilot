## Purpose

Minimal context for AI coding agents to be productive in this repository.

## What This Repo Does

Outputs are Construct 3 clipboard JSON (events, object-types, layouts). Paste into the C3 editor (Event sheet margin, Project Bar, Layout view).

## Read First

- `.claude/plugins/construct3-copilot/skills/c3-create/SKILL.md` — execution workflow, helper scripts, hard boundaries
- `.claude/plugins/construct3-copilot/CLAUDE.md` — strict generation constraints and hallucination traps

## Mandatory Workflow

```
QUERY → GENERATE → VALIDATE → FIX
```

1. Resolve every ACE ID via RAG lookup before using it — never guess
2. Generate clipboard JSON following clipboard format conventions
3. Validate output — fail = do not deliver
4. Include paste location and manual verification step in every response

## Key Commands

```bash
# ACE lookup via RAG (MANDATORY) — name the plugin or behavior first
python .claude/plugins/construct3-copilot/scripts/query/rag.py search "{addon} {keywords}"
python .claude/plugins/construct3-copilot/scripts/query/rag.py verify {addon}:{ace-id}

# Generate placeholder art
python ../Construct3-Clipboard/scripts/imagedata.py --color red --width 64 --height 64
```

## Conventions

- Do not invent ACE IDs — always query RAG first
- RAG looks ACEs up and declines how-to questions; read `../Construct3-Manual` or `../Construct-Example-Projects` for those
- Output clipboard JSON fragments only, not `.c3p` archives
- Run validation before returning any JSON
- Produce only Construct 3 output — no other engines

## Where to Look

- Plugin & skills: `.claude/plugins/construct3-copilot/`
- Scripts: `.claude/plugins/construct3-copilot/scripts/`
- Test fixtures: `tests/fixtures/`
- Game examples: `tests/examples/`
- Full project tools, editor previews and input validation: `../Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/SKILL.md`
