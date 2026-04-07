name: c3-create
description: >
  Generate paste-ready Construct 3 clipboard JSON (event sheets, objects, layouts) from natural
  language game descriptions. Handles platformers, shooters, puzzles, UI systems, and game logic.
  生成 Construct 3 剪贴板 JSON：事件表、对象、布局。支持平台跳跃、射击、解谜、UI 系统。
triggers:
  keywords:
    - construct 3
    - c3
    - event sheet
    - clipboard json
    - platformer
    - shooter
    - rpg game
    - puzzle game
    - breakout
    - tower defense
    - sprite
    - behavior
    - animation
    - collision
    - spawn
    - bullet
    - platform movement
    - 8direction
    - tween
    - keyboard input
    - mouse click
    - touch controls
    - gamepad
    - save load
    - inventory
    - dialogue system
    - particle
    - audio
    - multiplayer
    - 事件表
    - 场景
    - 布局
    - 精灵
    - 行为
    - 平台游戏
    - 射击游戏
    - 塔防
    - 玩法
    - 碰撞
    - 动画
    - 物理
    - 对话系统
    - 背包系统
  intents:
    - generate_c3_json
    - paste_to_c3
    - create_event_sheet
    - create_game_logic
---

# Create — Generate Construct 3 Game Content

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` first — it contains hallucination traps and the mandatory workflow.

## Workflow

DISCOVER → QUERY → GENERATE → VALIDATE → FIX

```bash
# 0. Service discovery
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/infra/health.py --brief

# 1. ACE lookup (mandatory)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py search {keyword}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}
# When RAG online:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}

# 2. Generate
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/imagedata.py --color {c} --width {W} --height {H}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/layout.py --preset {preset} -W {W} -H {H}
# When Clipboard online:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py generate '{ir}'

# 4. Validate (mandatory)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate/output.py '{json}'
# When Clipboard online:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'
```

## References

All clipboard format knowledge lives in `Construct3-Clipboard/docs/` (sibling repo):

| When | Read from Construct3-Clipboard |
|------|------|
| JSON format | `docs/clipboard-format.md` |
| Object templates | `docs/object-templates.md` |
| Layout templates | `docs/layout-templates.md` |
| End-to-end examples | `docs/examples.md` |
| Prompt templates | `docs/prompts.md` |
| Family patterns | `docs/family-patterns.md` |
| Deprecated features | `docs/deprecated-features.md` |

## Memory Context

On skill trigger: find `.c3proj` in project root, read its `uniqueId`. If `{project_root}/.claude/memory/memory.md` exists, read it for project context.

## Boundaries

- Output: Construct 3 clipboard JSON only (events, object-types, layouts, world-instances, event-sheets)
- Images: Placeholder geometric shapes only — no pixel art, no AI art
- Engine: Construct 3 only
- Validation: must pass validate/output.py before delivery
