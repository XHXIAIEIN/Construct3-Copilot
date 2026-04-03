name: construct3-copilot
description: >
  Construct 3 游戏开发助手。生成可直接粘贴到 C3 编辑器的剪贴板 JSON（事件表、对象、布局）。
  适用于：游戏逻辑（移动、碰撞、计分）、角色控制（键盘、鼠标、触摸）、UI 界面、场景布局。
  Generates Construct 3 clipboard JSON for events, objects, layouts. Game logic,
  character control, collision, scoring, UI elements, and level design.
triggers:
  keywords:
    # English - Core
    - construct 3
    - c3
    - event sheet
    - clipboard json
    # English - Game Types
    - platformer
    - shooter
    - rpg game
    - puzzle game
    - breakout
    - tower defense
    # English - Features
    - sprite
    - behavior
    - animation
    - physics
    - collision
    - spawn
    - bullet
    - platform movement
    - 8direction
    - pathfinding
    - tween
    # English - Input
    - keyboard input
    - mouse click
    - touch controls
    - gamepad
    # English - Systems
    - save load
    - inventory
    - dialogue system
    - particle
    - audio
    - multiplayer
    # 中文
    - 事件表
    - 场景
    - 布局
    - 精灵
    - 行为
    - 平台游戏
    - 射击游戏
    - 角色扮演
    - 塔防
    - 玩法
    - 碰撞
    - 动画
    - 物理
    - 粒子效果
    - 对话系统
    - 背包系统
  intents:
    - generate_c3_json
    - paste_to_c3
    - create_event_sheet
    - create_game_logic
---

# Construct 3 Copilot

Generate paste-ready Construct 3 clipboard JSON (event sheets, object types, layouts) and guide addon SDK development.

## 1. Load Constraints

Read @CLAUDE.md — it contains hallucination traps, mandatory workflow, and the pre-output checklist. Skip nothing.

## 2. Script Toolkit

All scripts: stdout = structured data, stderr = logs, exit 0 = success. `query/` scripts are read-only and safe to run in parallel.

### Service Discovery (run first on each session)

```bash
python3 scripts/infra/health.py --brief
# Output: RAG:+ Clipboard:+ Local:+  (+ = available, - = offline)
```

### ACE Schema Lookup

```bash
# Local lookup — MANDATORY, always available
python3 scripts/query/schema.py plugin {name} {ace-id}
python3 scripts/query/schema.py behavior {name} {ace-id}
python3 scripts/query/schema.py search {keyword}

# RAG semantic search — use when RAG is online, especially for fuzzy/Chinese queries
python3 scripts/query/rag.py search "how to detect collision"
python3 scripts/query/rag.py lookup "Sprite" --plugin sprite
python3 scripts/query/rag.py list "Platform"
python3 scripts/query/rag.py verify {ace-id} --plugin {plugin}
```

### Real-world Usage Patterns

```bash
python3 scripts/query/examples.py action {ace_id}
python3 scripts/query/examples.py condition {ace_id}
python3 scripts/query/examples.py top actions 20
```

### JSON Generation

```bash
# Local generation (placeholder art, layout presets)
python3 scripts/generate/imagedata.py --color {color} --width {W} --height {H}
python3 scripts/generate/layout.py --preset {platformer|breakout} -W {W} -H {H}

# Clipboard service — when online, use for IR → validated JSON
python3 scripts/generate/clipboard_service.py generate '<intent-ir-json>'
```

### Validation

```bash
# Local validation — MANDATORY, always run before delivery
python3 scripts/validate/output.py '<json>'

# Clipboard service validation — when online, use as second opinion
python3 scripts/generate/clipboard_service.py validate '<clipboard-json>'
```

## 3. Reference Routing

| Task | Load |
|------|------|
| Detailed workflow (Intent IR, clarification, generation pipeline) | @references/instructions.md |
| JSON format rules + templates | @references/clipboard-format.md |
| Object type templates with imageData | @references/object-templates.md |
| Layout/world-instance templates | @references/layout-templates.md |
| Behavior ID → display name mapping | @references/behavior-names.md |
| Chinese term mapping | @references/zh-cn.md |
| Paste errors, debugging | @references/troubleshooting.md |
| End-to-end examples | @references/examples.md |
| Family system patterns | @references/family-patterns.md |
| Effects & shaders | @references/effects-guide.md |
| Prompt templates (clarification, generation, review) | @references/prompts.md |
| Addon SDK development | @references/addon-sdk-index.md |
| Runtime scripting API | @references/runtime-api.md |

## 4. Boundaries

- **Output**: Construct 3 clipboard JSON only (events, object-types, layouts, world-instances, event-sheets, conditions, actions)
- **Images**: Placeholder geometric shapes only via `scripts/generate/imagedata.py` — no pixel art, no AI-generated art
- **Engine**: Construct 3 only — no Phaser, Unity, Godot
- **Validation**: JSON must pass `scripts/validate/output.py` before delivery. Fail = do not deliver
