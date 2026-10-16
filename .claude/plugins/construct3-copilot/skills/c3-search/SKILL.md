---
name: c3-search
description: >
  Search Construct 3 ACE definitions and explain plugin/behavior capabilities.
  搜索 Construct 3 ACE 定义，解释插件/行为功能。
triggers:
  keywords:
    - search ace
    - what actions
    - what conditions
    - list expressions
    - explain behavior
    - how to use
    - plugin capabilities
    - find action
    - ACE 查询
    - 有哪些动作
    - 有哪些条件
    - 怎么用
    - 什么表达式
    - can c3 do
    - does c3 support
    - c3 feature
    - 能不能做
    - 支不支持
    - 有没有
    - c3 3d
  intents:
    - search_ace
    - explain_plugin
    - find_usage
    - check_capability
---

# Search — Query Construct 3 ACE Documentation

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` for known hallucination traps (critical — wrong ACE IDs are the #1 failure mode).

## Capability Questions

Triggered by "C3 能不能做 X", "does C3 support X", or any feature inquiry.

**Hard rule: training data is stale for C3 features. Query first, answer second.**

1. `rag.py list {addon}` or `rag.py search "{addon} {keyword}"` — check the ACEs of the plugin or behavior the feature would belong to (≥1 query, max 3). RAG looks ACEs up and nothing else: it needs the addon's name and declines how-to and concept questions
2. Read the manual for feature docs — the `../Construct3-Manual/Construct3-Manual/` clone, or context7 `query-docs` on `/xhxiaiein/construct3-manual` (≥1 query, max 2)
3. Answer citing specific plugin names, ACE IDs, or scripting methods found in steps 1-2
4. If both sources return 0 relevant results → respond "文档中没有找到相关功能，建议查看 construct.net 官方更新日志确认"

**Escalate when:**
- RAG offline AND the manual returns 0 results → tell user, do not fall back to training data
- User claims a feature exists but docs don't show it → ask user for a link or example project, do not confirm or deny from memory

## When RAG Declines

A `rag.py` answer without a `lookup` section means RAG found no ACE by those words or declined the question. It is not evidence that Construct 3 lacks the feature, and asking RAG again in other words returns the same. Answer from what can be read:

| Question | Read |
|----------|------|
| What an addon does, how a feature works | `../Construct3-Manual/Construct3-Manual/` — one page per addon in `plugin-reference/` and `behavior-reference/`, plus `system-reference/`, `scripting/`, `tips-and-guides/` |
| How to build something ("enemy patrol", "save system") | `../Construct-Example-Projects/example-projects/{id}/eventSheets/`; find `{id}` by `tags` and `used-addons` in `../Construct3-RAG/data/c3-examples/en-US/*.json` |
| Which addon has the feature | `plugin-reference.md` and `behavior-reference.md` in the manual, then `rag.py list {addon}` |

Confirm every ACE ID taken from the manual or an example with `rag.py verify` before citing it.

## Scripts

```bash
# ACE lookup via RAG service
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {addon}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search "{addon} {keywords}"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py verify {addon}:{ace-id}
```

`{addon}` is a plugin or behavior id or its English display name. `--lang zh` adds the Chinese names. Query rules and output: `${CLAUDE_PLUGIN_ROOT}/scripts/query/README.md`.

## Memory Context

On skill trigger: find `.c3proj` in the working directory or one level up. If not found, skip memory loading. If found, read its `uniqueId` and check `{project_root}/.claude/memory/memory.md` — if it exists, read it for project context.

## Service Dependencies

Requires RAG service (port 8765). If offline, guide the user:
- Start: `cd ../Construct3-RAG && python -m uvicorn src.api:app --host 127.0.0.1 --port 8765`
- First time? Run `bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh` to clone all deps, including the manual and the example projects read above.

## Boundaries

- Read-only — does NOT generate clipboard JSON (use `/c3-create` for that)
- Does NOT modify any files
- Returns ACE definitions, parameters, usage examples, and explanations

## Routing

If the user asks "what actions does Sprite have?" → this skill (search/explain).
If the user asks "create a platformer with Sprite" → `/c3-create` (generation).
If the query is ambiguous ("I need collision detection"), start here to search, then hand off to `/c3-create` if the user wants to generate JSON.
