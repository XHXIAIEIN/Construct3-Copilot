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

## References

SDK documentation and templates are read from the sibling clones. RAG holds the ACE schemas of the built-in addons only and declines SDK questions, so do not send them to `rag.py`.

| Need | Read |
|------|------|
| Guides: addon metadata, defining ACEs, language file, runtime and editor scripts, porting to SDK v2 | `../Construct3-Manual/Construct3-Addon-SDK/guide/` |
| Editor API reference: `IPluginInfo`, `IBehaviorInfo`, base classes, editor interfaces | `../Construct3-Manual/Construct3-Addon-SDK/reference/` |
| Runtime API, the same one Construct's scripting feature uses | `../Construct3-Manual/Construct3-Manual/scripting/` |
| Working templates, and the JSON schemas for `aces.json`, `addon.json` and language files | `../Construct-Addon-SDK/` — `plugin-sdk/`, `behavior-sdk/`, `effect-sdk/`, `theme-sdk/` |
| TypeScript definitions of the SDK | `../Construct3-RAG/data/c3-ts-defs/sdk/` (editor), `../Construct3-RAG/data/c3-ts-defs/preview/interfaces/sdk/` (runtime) |

Start from the template closest to the addon being built, and check every claim about the SDK against these files, not training data.

## Scripts

```bash
# How a built-in addon names and shapes its ACEs (a model for aces.json)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {addon}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search "{addon} {keywords}"
```

If a clone is missing, or RAG is offline, guide the user:
- First time? Run `bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh` to clone all deps.
- Start RAG: `cd ../Construct3-RAG && python -m uvicorn src.api:app --host 127.0.0.1 --port 8765`

## Addon Types

| Type | Purpose | Key Files |
|------|---------|-----------|
| Plugin | New object type | plugin.js, type.js, instance.js |
| Behavior | Attachable behavior | behavior.js, type.js, instance.js |
| Effect | WebGL/WebGPU shader | effect.fx, effect.wgsl |

## Memory Context

On skill trigger: find `.c3proj` in the working directory or one level up. If not found, skip memory loading. If found, read its `uniqueId` and check `{project_root}/.claude/memory/memory.md` — if it exists, read it for project context.

## Boundaries

- Addon SDK v2 only (not v1)
- Does NOT generate clipboard JSON (use c3-create)
- Does NOT validate clipboard JSON (use c3-validate)
- Outputs: addon file structure + JavaScript/TypeScript code + aces.json + lang files
