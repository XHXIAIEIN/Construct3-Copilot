# Data Source Redesign

## Problem

Plugin scripts depend on `data/schemas/` and `data/project_analysis/` — directories removed from git in Phase 0 (`1c43823`). Scripts work only because stale copies remain on disk. A fresh clone breaks `schema.py`, `examples.py`, and `validate/output.py` layer 3.

Additionally, several scripts are dead code: `clipboard.py` (empty skeleton), `paste.py` (macOS-only, dev is on Windows), `bridge.py` (replaced by MCP).

## Decision

- **Schema source of truth:** `Construct3-RAG/data/c3-schemas/` (sibling repo)
- **Discovery mechanism:** env var → sibling directory convention → error with clone suggestion (Option A)
- **Schema format:** Read RAG's original format directly (en-US primary, zh-CN on demand). No intermediate build step.
- **Dead data:** `data/schemas/`, `data/project_analysis/` deleted
- **Dead scripts:** `examples.py`, `clipboard.py`, `paste.py`, `bridge.py` → `.trash/`

## Design

### 1. `scripts/_resolve.py` — Sibling Repo Discovery

Shared module imported by all scripts that need external data.

```
resolve_rag_root() -> Path:
    1. $C3_RAG_ROOT env var
    2. {copilot_repo_root}/../Construct3-RAG/
    3. raise RepoNotFoundError with clone suggestion

resolve_clipboard_root() -> Path:
    1. $C3_CLIPBOARD_ROOT env var
    2. {copilot_repo_root}/../Construct3-Clipboard/
    3. raise RepoNotFoundError with clone suggestion
```

Path calculation: `Path(__file__).parent` (scripts/) → `.parent.parent.parent.parent` → repo root → `../{sibling}/`.

Error output format (consistent with existing scripts):
```json
{"error": "Construct3-RAG not found", "suggestion": "git clone <url> to Construct3-Copilot sibling directory, or set C3_RAG_ROOT env var"}
```

### 2. `schema.py` — Adapt to RAG Format

**Path change:**
```
Old: {repo_root}/data/schemas/{plugins,behaviors}/*.json
New: {rag_root}/data/c3-schemas/en-US/{plugins,behaviors}/*.json
     {rag_root}/data/c3-schemas/zh-CN/{plugins,behaviors}/*.json  (on demand)
```

**Field mapping:**

| RAG field | Usage |
|-----------|-------|
| `name` | Display name (English) |
| `description` | ACE description |
| `conditions`, `actions`, `expressions` | ACE lists |
| `params[].id`, `params[].type`, `params[].items` | Parameter details |

Chinese names: load corresponding file from `zh-CN/` directory, match ACEs by `id` field.

**Interface unchanged:** `schema.py search|plugin|behavior` signatures stay the same. Callers (SKILL.md, CLAUDE.md) need no changes to command invocations.

### 3. `validate/output.py` — Layer 3 Schema Path

Layer 3 (ACE ID cross-check) currently resolves `data/schemas/` from script location. Change to use `_resolve.py` to find RAG schemas. Layers 1-2 (structural + pitfalls) are unaffected.

Graceful degradation: if RAG repo not found, layers 1-2 still run. Layer 3 skipped with warning:
```
⚠ Schema cross-check skipped: Construct3-RAG not found
```

### 4. `health.py` — Check RAG Repo Instead of Local Data

Replace local data directory check with:
- RAG repo exists? (via `_resolve.py`)
- RAG schemas directory populated?

### 5. SKILL.md / CLAUDE.md Updates

Remove all references to:
- `examples.py` (search skill, create skill)
- `clipboard.py` (create skill)
- `paste.py`, `bridge.py` (not currently referenced, but verify)

## Change Manifest

| Action | File |
|--------|------|
| **Create** | `scripts/_resolve.py` |
| **Modify** | `scripts/query/schema.py` — use `_resolve.py`, adapt RAG format |
| **Modify** | `scripts/validate/output.py` — layer 3 path via `_resolve.py` |
| **Modify** | `scripts/infra/health.py` — check RAG repo existence |
| **Modify** | `skills/search/SKILL.md` — remove `examples.py` references |
| **Modify** | `skills/create/SKILL.md` — remove `examples.py`, `clipboard.py` references |
| **Modify** | `CLAUDE.md` — remove `examples.py` from workflow |
| **→ .trash/** | `data/schemas/`, `data/project_analysis/` |
| **→ .trash/** | `scripts/query/examples.py` |
| **→ .trash/** | `scripts/generate/clipboard.py` |
| **→ .trash/** | `scripts/infra/paste.py`, `scripts/infra/bridge.py` |
| **No change** | `scripts/query/rag.py` |
| **No change** | `scripts/generate/clipboard_service.py`, `imagedata.py`, `layout.py` |
| **No change** | `scripts/validate/output.py` layers 1-2 |

## Out of Scope

- RAG service hosting (stays localhost:8765)
- Clipboard service hosting (stays localhost:8766)
- `rag.py` / `clipboard_service.py` refactoring (already correct as HTTP clients)
- Community distribution (current target: developer self-use with clone)
