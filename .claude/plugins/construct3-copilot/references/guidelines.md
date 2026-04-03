# Construct 3 Copilot Skill Governance

Checklist for maintaining skill files. Follow when editing SKILL.md, CLAUDE.md, instructions, or references.

## 1. Discovery Metadata
- Keep `name`, `description`, and `triggers` in SKILL.md focused on Construct 3 clipboard workflows
- Description must include verbs ("generate", "validate") and nouns ("Construct 3", "clipboard JSON") that appear in user prompts
- Update `triggers.keywords` when adding new capabilities

## 2. Progressive Disclosure
- SKILL.md: concise entry point (<120 lines including frontmatter), points to references
- CLAUDE.md: hard constraints only (<70 lines)
- Detailed workflows, prompts, schemas, examples → `references/`
- Scripts → `scripts/` (never duplicate inline)

## 3. Single Source of Truth
- ACE retrieval rules + hallucination traps → CLAUDE.md only
- Script paths + reference routing → SKILL.md only
- Workflow details + design principles → references/instructions.md only
- Do not duplicate information across files. Cross-reference with `@filename`.

## 4. Script Inventory
Scripts live in `scripts/` with this structure:

| Directory | Purpose | Parallel-safe |
|-----------|---------|---------------|
| `scripts/query/` | ACE schema lookup, example mining, RAG | Yes (read-only) |
| `scripts/generate/` | ImageData, layouts, clipboard payloads | Caution |
| `scripts/validate/` | JSON validation | Yes (read-only) |
| `scripts/infra/` | Bridge server, health checks, paste automation | Caution |

Convention: stdout = structured data, stderr = logs, exit 0 = success.

## 5. Validation Workflow
1. Generate JSON
2. Run `scripts/validate/output.py '<json>'`
3. If touching layouts/imageData, regenerate previews via `scripts/generate/`
4. Include at least one manual verification step in final response

## 6. Testing
- `tests/test_skill.py` must pass locally after changes
- Large scenario changes → document in `.local/skill-validation-report.md`
- Regression fixtures go in `tests/examples/`
