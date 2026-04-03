# query/ — ACE Retrieval Scripts

Read-only scripts for querying Construct 3 ACE schemas and real-world usage patterns.
All scripts are safe to run in parallel.

---

## schema.py — ACE Schema Lookup

Confirms plugin/behavior condition, action, and expression IDs and their parameters.

**When to use**: Before generating any ACE ID; when user asks "is there an action for X"; when unsure about parameter format.
**When NOT to use**: ACE ID already confirmed in this conversation turn.

```bash
python3 scripts/query/schema.py search <keyword>           # fuzzy search
python3 scripts/query/schema.py plugin <name> [ace-id]     # plugin ACE
python3 scripts/query/schema.py behavior <name> [ace-id]   # behavior ACE
```

| User says | Run |
|-----------|-----|
| "Is there a set-animation action?" | `schema.py search animation` |
| "What conditions does Platform have?" | `schema.py behavior platform` |
| "What params does on-click need?" | `schema.py plugin mouse on-click` |

**Not found = does not exist.** Never guess an ACE ID that schema.py cannot find.

---

## examples.py — Real-World Usage Mining

Mines ACE usage patterns from `data/project_analysis/*.json`.

**When to use**: Need typical parameter combinations for an ACE; user asks "how do others use X".
**When NOT to use**: `data/project_analysis/` does not exist (run `infra/health.py` to check); only need to confirm an ID exists (use schema.py instead).

```bash
python3 scripts/query/examples.py action <ace-id>          # action usage
python3 scripts/query/examples.py condition <ace-id>        # condition usage
python3 scripts/query/examples.py top actions 20            # most-used actions
```

---

## rag.py — RAG Semantic Search [not ready]

Semantic search over Construct 3 documentation. Requires vector DB backend (not configured).

**When to use**: Open-ended questions ("how to implement enemy AI patrol") that schema.py cannot answer.
**When NOT to use**: Current version — returns "backend not configured" error.

```bash
python3 scripts/query/rag.py "how to implement pathfinding"
```

---

## Anti-patterns

- Using an ACE ID after schema.py returns empty results
- Writing ACE conditions/actions without running schema.py first
- Treating examples.py output as the only valid usage (it is reference, not spec)
