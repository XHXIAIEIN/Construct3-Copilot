# Construct 3 Copilot Skill Governance

This checklist merges the Claude Agent Skills best practices (`code.claude.com/docs/en/skills`) and the Codex Agent Skills specification (`developers.openai.com/codex/skills`). Follow it whenever you edit `SKILL.md`, prompts, instructions, or references.

## 1. Discovery Metadata
- Keep `name`, `description`, and `triggers` focused on Construct 3 clipboard workflows so both runtimes can auto-select the skill.
- Description should include the verbs (“generate”, “validate”, “layout”) and nouns (“Construct 3”, “clipboard JSON”) that appear in user prompts.
- Update `triggers.keywords` or `triggers.intents` whenever you add new capabilities (e.g., imageData generation).

## 2. Progressive Disclosure Structure
- `SKILL.md` stays concise (< ~400 lines) and only points to external references.
- Detailed workflows, prompts, schemas, and examples live under `references/` so the agent loads them on-demand.
- Scripts belong in `scripts/` and must be referenced (not duplicated) inside instructions.

## 3. Canonical References
- `references/instructions.md` = execution workflow.
- `references/prompts.md` = clarification, generation, and self-review prompts.
- `references/examples/` = paste-ready clipboard JSON (layouts + events) paired with Intent IR notes.
- `references/clipboard-format.md` = ACE parameter grammar; never redefine this elsewhere.
- cite official docs when adding new sections so future maintainers know whether guidance came from Claude or Codex.

## 4. Semantic Contracts
- Always mention when optional dependencies (e.g., `scripts/query_examples.py` for RAG) are available; guard their usage with existence checks.
- Call out unsupported scopes (“no Phaser exports”) in `instructions.md` so agents avoid misfiring the skill.
- When you add new objects/behaviors, mirror the vocabulary used in `data/schemas` to keep ACE IDs stable.

## 5. Validation Workflow
1. Generate plan + Intent IR.
2. Produce JSON.
3. Run `.claude/skills/construct3-copilot/scripts/validate_output.py '<json>'`.
4. If JSON touches layouts or imageData, regenerate previews via `scripts/generate_layout.py` or `scripts/generate_imagedata.py` and store the artifact under `references/examples/`.
5. Document at least one manual verification step inside your final response.

## 6. Testing Expectations
- `tests/test_skill.py` must pass locally; update it when you add new scripts or schema requirements.
- Large scenario changes should get copied into `.local/skill-validation-report.md` with rationale + paste steps.
- When the user requests “real scenarios,” add a dedicated regression under `tests/` or provide a replay JSON in `.local/` they can paste.

Keep this file updated whenever Claude or Codex change their published best practices.
