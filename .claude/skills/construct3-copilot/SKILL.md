name: construct3-copilot
description: >
  Construct 3 游戏开发助手。生成可直接粘贴到 C3 编辑器的剪贴板 JSON（事件表、对象、布局）。
  适用于：游戏逻辑（移动、碰撞、计分）、角色控制（键盘、鼠标、触摸）、UI 界面、场景布局。
  Generates Construct 3 clipboard JSON for events, objects, layouts. game logic,
  character control, collision, scoring, UI elements, and level design.
triggers:
  keywords:
    - construct 3
    - c3
    - event sheet
    - 事件表
    - 场景
    - 精灵
    - 行为
    - 玩法
    - 目标
    - 逻辑
    - 移动
    - 控制
    - 碰撞
  intents:
    - generate_c3_json
    - paste_to_c3
---

# Execution Instructions

## 1. Load Constraints

Read @CLAUDE.md for workflow rules (Intent IR, Clarification, output format).

## 2. Available Scripts

```bash
# ⚠️ 必须先检索再生成！禁止凭记忆猜测 ACE ID

# ACE schema lookup (确认 ACE ID 存在)
python3 scripts/query_schema.py plugin {name} {ace}
python3 scripts/query_schema.py behavior {name} {ace}
python3 scripts/query_schema.py search {keyword}

# 案例库查询 (学习真实用法，403 个官方项目)
python3 scripts/query_examples.py action {ace_id}
python3 scripts/query_examples.py condition {ace_id}
python3 scripts/query_examples.py top actions 20

# ImageData generation
python3 scripts/generate_imagedata.py --color {color} --width {W} --height {H}
python3 scripts/generate_imagedata.py --kenney {preset} --color {color}

# Layout presets
python3 scripts/generate_layout.py --preset {platformer|breakout} -W {W} -H {H}

# Validate before output
python3 scripts/validate_output.py '<json>'
```

## 3. Reference Files

### Core References
| When | Load |
|------|------|
| JSON format rules | @references/clipboard-format.md |
| Object templates | @references/object-templates.md |
| Layout templates | @references/layout-templates.md |
| Behavior mapping | @references/behavior-names.md |
| Chinese terms | @references/zh-cn.md |
| Error debugging | @references/troubleshooting.md |
| Full examples | @references/examples.md |

### Advanced Topics
| When | Load |
|------|------|
| Multi-layer layouts (Background/Game/UI) | @references/multi-layer-layouts.md |
| Complete game levels | @references/complete-levels.md |
| Multiplayer networking | @references/multiplayer-patterns.md |
| Complex state management | @references/limitations-and-refinement.md |
| Prompt patterns & templates | @references/prompt-patterns.md |
| Advanced JSON examples | @references/advanced-examples.md |

## 4. Boundaries

- Output: Clipboard JSON only (events, objects, layouts)
- Images: Placeholder shapes only (no real art)
- Engine: Construct 3 only
