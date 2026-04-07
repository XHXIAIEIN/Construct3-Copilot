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
  intents:
    - search_ace
    - explain_plugin
    - find_usage
---

# Search — Query Construct 3 ACE Documentation

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` for known hallucination traps (critical — wrong ACE IDs are the #1 failure mode).

## Scripts

```bash
# ACE lookup via RAG service
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {plugin}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py lookup {query} --plugin {plugin}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py verify {ace-id} --plugin {plugin}
```

## Memory Context

On skill trigger: find `.c3proj` in the working directory or one level up. If not found, skip memory loading. If found, read its `uniqueId` and check `{project_root}/.claude/memory/memory.md` — if it exists, read it for project context.

## Service Dependencies

Requires RAG service (port 8765). If offline, guide the user:
- Start: `cd ../Construct3-RAG && python src/api.py`
- First time? Run `bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh` to clone all deps.

## Boundaries

- Read-only — does NOT generate clipboard JSON (use `/c3-create` for that)
- Does NOT modify any files
- Returns ACE definitions, parameters, usage examples, and explanations

## Routing

If the user asks "what actions does Sprite have?" → this skill (search/explain).
If the user asks "create a platformer with Sprite" → `/c3-create` (generation).
If the query is ambiguous ("I need collision detection"), start here to search, then hand off to `/c3-create` if the user wants to generate JSON.
