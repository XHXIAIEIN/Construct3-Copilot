# query/ — ACE Retrieval Scripts

Read-only scripts for querying Construct 3 ACE schemas and real-world usage patterns.
All scripts are safe to run in parallel.

---

## rag.py — ACE Schema Lookup & Semantic Search

All ACE queries go through `rag.py`. Confirms plugin/behavior condition, action, and expression IDs and their parameters. Also supports semantic search over Construct 3 documentation.

**When to use**: Before generating any ACE ID; when user asks "is there an action for X"; when unsure about parameter format; open-ended questions ("how to implement enemy AI patrol").
**When NOT to use**: ACE ID already confirmed in this conversation turn.

```bash
python3 scripts/query/rag.py search <keyword>                    # fuzzy search
python3 scripts/query/rag.py lookup <ace-id> --plugin <name>     # plugin ACE
python3 scripts/query/rag.py list <plugin-or-behavior>           # list all ACEs
python3 scripts/query/rag.py verify <ace-id> --plugin <name>     # verify ACE exists
```

| User says | Run |
|-----------|-----|
| "Is there a set-animation action?" | `rag.py search animation` |
| "What conditions does Platform have?" | `rag.py list platform` |
| "What params does on-click need?" | `rag.py lookup on-click --plugin mouse` |

**Not found = does not exist.** Never guess an ACE ID that rag.py cannot find.

---

## Anti-patterns

- Using an ACE ID after rag.py returns empty results
- Writing ACE conditions/actions without running rag.py first
- Treating RAG search results as the only valid usage (they are reference, not spec)
