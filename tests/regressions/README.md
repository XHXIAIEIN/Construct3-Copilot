# Regression Workflow

Use this directory to keep quality stable when new failure modes appear.

## Files

- `failure_cases.jsonl`: Known failure signatures and fixes. One JSON object per line.

## Update Rule

1. When a user-facing generation fails, add a new case to `failure_cases.jsonl`.
2. Include: `case_id`, `query`, `error_signature`, `root_cause`, `fix`, and `tags`.
3. Add or update a reproducible JSON fixture in `tests/examples/` or `tests/fixtures/`.
4. Run: `python -m pytest tests/`
