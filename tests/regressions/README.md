# Regression Workflow

Use this directory to keep quality stable when new failure modes appear.

## Files

- `failure_cases.jsonl`: Known failure signatures and fixes. One JSON object per line.

## Update Rule

1. When a user-facing generation fails, add a new case to `failure_cases.jsonl`.
2. Include: `case_id`, `query`, `error_signature`, `root_cause`, `fix`, and `tags`.
3. Add or update a reproducible JSON fixture in `tests/examples/` or `tests/fixtures/`.
4. Run:
   - `python scripts/validate_skill_docs.py`
   - `python -m unittest tests.test_fixtures`

You can append a new case with:

```bash
python scripts/log_failure_case.py \
  --case-id missing-player-object \
  --query "Top-down shooter spawn bullet" \
  --signature "unknown objectClass 'Player'" \
  --root-cause "Output referenced object before definition" \
  --fix "Include object-types for Player before events" \
  --tags events,objects,dependency
```

## Similar-case Lookup

```bash
python scripts/find_similar_failures.py "toggle boolean pause"
```
