# Scripts — Construct 3 Copilot Toolkit

Atomic CLI scripts for querying, generating, and validating Construct 3 clipboard JSON.

## Directory Index

| Directory | Purpose | Parallel-safe |
|-----------|---------|---------------|
| `query/` | ACE lookup via RAG service | Yes (read-only) |
| `generate/` | Placeholder images, layout presets, clipboard service bridge | Caution |
| `infra/` | Health checks | Yes (read-only) |

## Mandatory Workflow

```
QUERY → GENERATE → VALIDATE → FIX
```

1. **Query** `rag.py` to confirm every ACE ID before generation
2. **Generate** JSON via scripts or direct authoring
3. **Validate** with `clipboard_service.py validate` — fail means do not deliver
4. **Fix** on failure, then re-validate (loop step 3)

## Calling Convention

- stdout = structured data, stderr = logs
- exit 0 = success, non-zero = failure
- `query/` scripts are read-only — safe to run in parallel
