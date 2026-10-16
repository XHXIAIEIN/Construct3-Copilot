# query/ — ACE Retrieval Scripts

Read-only scripts for querying Construct 3 ACE schemas.
All scripts are safe to run in parallel.

For project authoring, editor checks and previews, follow the sibling
`Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/SKILL.md`.
Its scripts read bundled data directly; the HTTP bridge below serves the
clipboard workflow.

---

## rag.py — ACE Schema Lookup

All ACE queries go through `rag.py`, a bridge to the Construct3-RAG lookup service. It confirms which conditions, actions and expressions an addon (plugin or behavior) has, with their IDs and parameters.

**When to use**: Before generating any ACE ID; when user asks "is there an action for X"; when unsure about parameter format.
**When NOT to use**: ACE ID already confirmed in this conversation turn; how-to and concept questions ("how to implement enemy AI patrol"), which the service declines — see [What the lookup declines](#what-the-lookup-declines).

```bash
python3 scripts/query/rag.py list <addon>                   # ACE names of one addon, by type
python3 scripts/query/rag.py search "<addon> <keywords>"    # matching ACEs with IDs and params
python3 scripts/query/rag.py verify <addon>:<ace-id>        # exact ID check, exit 1 if absent
```

`lookup` does the same as `search`, and so does a query without a subcommand.

| User says | Run |
|-----------|-----|
| "Is there a set-animation action?" | `rag.py search "Sprite animation"` |
| "What conditions does Platform have?" | `rag.py list Platform` |
| "What params does on-click need?" | `rag.py verify mouse:on-click` |
| "What is key-is-down called in Chinese?" | `rag.py verify keyboard:key-is-down --lang zh` |

### Writing a query

- Name the addon first, by id (`EightDir`) or English display name (`"8 Direction"`). A query that names no addon is declined. These names address the schema only: `behaviorType` in clipboard JSON stays `8Direction`.
- Keywords are words from the ACE name (`animation`, `max speed`), not its hyphenated ID. Check an ID with `verify`.
- Use at most three keywords, and prefer the distinctive word: `set` alone matches dozens of actions.
- `--lang zh` adds the Chinese names under `name.zh`. Without it the language is detected from the query, so an English query returns English names only. `list` prints English names in every language.
- `--scope scripts` adds each ACE's `script_name`.

### verify

`verify` compares IDs exactly. `toggle-boolean` fails although `toggle-boolean-eventvar` exists, and the real ID comes back under `nearest`.

It compares IDs in the addon's complete lookup response, including only the `_common` ACEs listed in that addon's schema. A `_common` hit carries a `note`. An addon the service does not recognize never verifies, whatever the ID.

| Result | Exit | Output |
|--------|------|--------|
| ID exists | 0 | `{"verified": true, "matches": [{"addon", "ace_type", "ace_id", "name", "params", ...}]}` |
| ID or addon missing | 1 | `{"verified": false, "error", "suggestion", "nearest"}` |

**Rejected by `verify` = does not exist.** Never use that ACE ID, and never guess another.

### What the lookup declines

An answer without a `lookup` section, with a note on stderr, means the service found no ACE by those words or declined the question: no addon named, more than three keywords, or a how-to or concept question. It does not mean Construct 3 lacks the feature.

Asking again in other words returns the same. Read instead:

- `rag.py list <addon>` — every ACE name of the addon
- `../Construct3-Manual/Construct3-Manual/` — `plugin-reference/`, `behavior-reference/`, `system-reference/`, `scripting/`, `tips-and-guides/`
- `../Construct-Example-Projects/example-projects/<id>/eventSheets/` — how official examples build it; `../Construct3-RAG/data/c3-examples/en-US/<id>.json` lists each example's `tags` and `used-addons`

---

## Anti-patterns

- Using an ACE ID that `verify` rejected, or one seen only as part of a longer ID
- Writing ACE conditions/actions without running rag.py first
- Reading an answer without a `lookup` section as "Construct 3 cannot do this"
- Rephrasing a declined question for rag.py instead of reading the manual or the examples
