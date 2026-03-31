# Recovery And Regression Playbook

Use this playbook when generation quality drops or user requests go out of scope.

## A. Scope-Breach Decision Tree

1. Validation fails due unknown ACE ID:
   - Re-run schema lookup.
   - Replace ACE with schema-confirmed equivalent.
2. Validation fails due missing objects/variables:
   - Add required definitions in the same payload or ask user to confirm existing names.
3. User asks unsupported output (non-Construct 3 engine / production art):
   - Return in-scope alternative and state boundary.

## B. Retry Loop (max 2 automatic retries)

1. Collect validator errors.
2. Map each error to a fix pattern from `tests/regressions/failure_cases.jsonl`.
3. Regenerate JSON with explicit fixes.
4. Re-run validator.
5. If still failing after 2 retries, stop and ask one targeted clarification question.

## C. Similar-Case Retrieval

```bash
python scripts/find_similar_failures.py "<error signature>"
```

Use top matches as deterministic fix hints before re-generation.

## D. Post-Fix Actions

1. Add a new entry in `tests/regressions/failure_cases.jsonl` when a new pattern appears.
   - Preferred command:
     `python scripts/log_failure_case.py --case-id <id> --query "<query>" --signature "<error>" --root-cause "<cause>" --fix "<fix>" --tags tag1,tag2`
2. Add/update fixtures under `tests/examples/` or `tests/fixtures/`.
3. Run:
   - `python scripts/validate_skill_docs.py`
   - `python -m unittest tests.test_fixtures`
