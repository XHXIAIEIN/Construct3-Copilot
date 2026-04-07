# generate/ — Resource Generation Scripts

Generates Construct 3 clipboard JSON via the Clipboard service.
Always run `query/rag.py` to confirm ACE IDs before generating.

## clipboard_service.py — Clipboard Service Bridge

HTTP bridge to the Clipboard service (default port 8766, override with `C3_CLIPBOARD_PORT`).

```bash
python3 scripts/generate/clipboard_service.py generate '{"intent": "..."}'
python3 scripts/generate/clipboard_service.py validate '{"is-c3-clipboard-data":true,...}'
python3 scripts/generate/clipboard_service.py health
```

## Generation Workflow (mandatory order)

1. `query/rag.py` — confirm all ACE IDs exist
2. `generate/clipboard_service.py generate` — produce clipboard JSON
3. `generate/clipboard_service.py validate` — validate output; fix and re-validate on failure

## Anti-patterns

- Writing ACE conditions/actions into JSON without schema confirmation
- Delivering JSON without running `clipboard_service.py validate`
- Delivering JSON when validation reports errors
