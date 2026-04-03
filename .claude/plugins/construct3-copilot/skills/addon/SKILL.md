name: c3-addon
description: >
  Guide development of custom Construct 3 plugins and behaviors using the Addon SDK v2.
  Generates file structure, aces.json, language files, runtime scripts, and editor scripts.
  指导 Construct 3 自定义插件和行为开发（Addon SDK v2）。
triggers:
  keywords:
    - addon sdk
    - custom plugin
    - custom behavior
    - write plugin
    - write behavior
    - aces.json
    - addon.json
    - editor scripts
    - runtime scripts
    - c3runtime
    - 插件开发
    - 自定义行为
    - 自定义插件
  intents:
    - develop_addon
    - create_plugin
    - create_behavior
---

# Addon — Construct 3 Plugin/Behavior Development

## Scripts

```bash
# Search SDK documentation (when RAG online)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}
```

## References

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/addon-sdk-index.md |
| Guides | @${CLAUDE_PLUGIN_ROOT}/references/addon-sdk/guide/ (all files) |
| API reference | @${CLAUDE_PLUGIN_ROOT}/references/addon-sdk/reference/ (all files) |
| Scripting API | @${CLAUDE_PLUGIN_ROOT}/references/runtime-api.md |

## Addon Types

| Type | Purpose | Key Files |
|------|---------|-----------|
| Plugin | New object type | plugin.js, type.js, instance.js |
| Behavior | Attachable behavior | behavior.js, type.js, instance.js |
| Effect | WebGL/WebGPU shader | effect.fx, effect.wgsl |

## Memory Context

On skill trigger: find `.c3proj` in project root, read its `uniqueId`. If `{project_root}/.claude/memory/memory.md` exists, read it for project context.

## Boundaries

- Addon SDK v2 only (not v1)
- Does NOT generate clipboard JSON (use c3-create)
- Does NOT validate clipboard JSON (use c3-validate)
- Outputs: addon file structure + JavaScript/TypeScript code + aces.json + lang files
