# infra/ — Infrastructure Scripts

Environment checks and external integrations. These have side effects — do not run blindly in parallel.

---

## health.py — Environment Health Check

Verifies that data files and dependencies required by the Copilot skill are present.

**When to use**: Other scripts error out (missing schema/examples data); user's first session; troubleshooting unexpected failures.
**When NOT to use**: Everything is running normally.

```bash
python3 scripts/infra/health.py
```

Output: `{"status": "ok"|"degraded", "checks": {...}}`

Checks:
- Construct3-RAG sibling repo — plugin/behavior schema JSON (required by schema.py)
- `references/` — reference doc completeness
- Required script files present
- Python >= 3.10

When `status: "degraded"`, report which capabilities are limited. Do not pretend everything works.

---

## paste.py — Clipboard Automation [shelved]

Writes JSON to system clipboard. Requires pyperclip.

**When to use**: User asks to auto-copy to clipboard.
**When NOT to use**: Currently shelved — recommend user manually copy the JSON code block.

---

## bridge.py — Browser Bridge [shelved]

WebSocket bridge for direct communication with Construct 3 editor. Not currently available.

---

## Anti-patterns

- Calling scripts that depend on missing data after health.py reports degraded
- Starting generation without telling the user about degraded status
