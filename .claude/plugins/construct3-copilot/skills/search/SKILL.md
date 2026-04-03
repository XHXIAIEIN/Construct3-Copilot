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
# Local ACE lookup (always available)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py search {keyword}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py behavior {name} {ace-id}

# RAG semantic search (when online — better for fuzzy/Chinese queries)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {plugin}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py lookup {query} --plugin {plugin}
```

## References

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md |
| Chinese queries | @${CLAUDE_PLUGIN_ROOT}/references/zh-cn.md |

## Memory Context

On skill trigger: find `.c3proj` in project root, read its `uniqueId`. If `{project_root}/.claude/memory/memory.md` exists, read it for project context.

## Boundaries

- Read-only — does NOT generate clipboard JSON (use c3-create)
- Does NOT modify any files
- Returns ACE definitions, parameters, usage examples, and explanations
