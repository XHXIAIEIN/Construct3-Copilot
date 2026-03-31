# Construct 3 Copilot Quality Governance

Use this checklist whenever you update `.agents/skills/construct3-copilot`.

## 1. Source Of Truth

- `data/schemas/` is the only ACE truth source.
- `SKILL.md` defines trigger scope and execution contract.
- `references/examples.md` and `references/layout-templates.md` are canonical paste examples.

## 2. Reliability Pipeline

1. Parse request into Intent IR (`references/intent_schema.json`).
2. Resolve ACE IDs with `.agents/skills/construct3-copilot/scripts/query_schema.py`.
3. Generate clipboard JSON.
4. Validate with `.agents/skills/construct3-copilot/scripts/validate_output.py`.
5. Run docs gate with `python scripts/validate_skill_docs.py`.

Never skip step 2 or step 4.

## 3. Out-Of-Scope And Recovery

When a request exceeds scope (unsupported engine/output, missing project prerequisites, repeated validation failures):

1. State the blocked boundary clearly.
2. Return the smallest validated JSON subset.
3. Ask one targeted clarification question.
4. Retry after clarification and include validation evidence.

## 4. Failure Library And Similar-Case Search

- Record every new failure pattern in `tests/regressions/failure_cases.jsonl`.
- Include: `case_id`, `query`, `error_signature`, `root_cause`, `fix`, `tags`.
- Preferred append command:

```bash
python scripts/log_failure_case.py --case-id <id> --query "<query>" --signature "<error>" --root-cause "<cause>" --fix "<fix>" --tags tag1,tag2
```
- Retrieve prior fixes before retrying:

```bash
python scripts/find_similar_failures.py "unknown action id toggle-boolean"
```

## 5. Regression Requirements

- Add or update reproducible fixtures under `tests/examples/` or `tests/fixtures/`.
- Ensure `python -m unittest tests.test_fixtures` passes.
- Ensure `python scripts/validate_skill_docs.py` passes.
- CI must fail on broken doc links or invalid clipboard examples.
