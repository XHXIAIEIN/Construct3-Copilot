# infra/ — Infrastructure Scripts

Dependency setup and read-only service probes for the clipboard workflow.

---

## health.py — Environment Health Check

Probes the RAG and Clipboard services at their `/health` endpoints.

**When to use**: Before a service call, or when a bridge reports a connection failure.
**When NOT to use**: Everything is running normally.

```bash
python3 scripts/infra/health.py
```

Output: `{"status": "ok"|"degraded", "services": {"rag": {...}, "clipboard": {...}}}`.
Each service reports its URL, availability and status. `--brief` prints
`RAG:+ Clipboard:+` with `-` for an unavailable service. The script exits 0
even when degraded; read the availability fields before calling a service.

The defaults are `127.0.0.1:8765` and `127.0.0.1:8766`. `C3_RAG_PORT` and
`C3_CLIPBOARD_PORT` override their ports.

When `status: "degraded"`, report which capabilities are limited. Do not pretend everything works.

---

## setup.sh — Sibling Dependencies

`bash scripts/infra/setup.sh --check` reports which sibling clones exist and
runs `pip check`. Without `--check`, it clones missing dependencies and
installs the service requirements. Sibling paths are resolved beside the
main checkout, including when Copilot runs in a Git worktree.

RAG supplies schema data and the optional lookup service. Agent-Skills
supplies project tools and prompts under
`Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/`. Clipboard
supplies fragment generation and structural validation. Manual, official
examples and Addon SDK supply reference material.

---

## welcome.sh — Session Context

Prints service availability, missing sibling repositories, available skills
and any existing profile or project context for the SessionStart hook.

---

## Anti-patterns

- Calling scripts that depend on missing data after health.py reports degraded
- Starting generation without telling the user about degraded status
