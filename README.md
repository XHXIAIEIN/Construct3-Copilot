# Construct 3 Copilot

[中文](README_CN.md) | **English**

Generate Construct 3 event sheet JSON with natural language, paste directly into editor.

## Quick Start

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot
claude
```

> Requires [Claude Code CLI](https://claude.ai/download)

## Usage Examples

**Complete Game**
```
> 做一个打砖块游戏，球拍跟随鼠标移动

AI generates:
- layout.json  → Paste to: Project Bar → Layouts
- events.json  → Paste to: Event sheet margin
```

**Add Feature**
```
> 添加 WASD 八方向移动控制

AI generates events JSON → Paste to: Event sheet margin
```

**UI Snippet**
```
> 加一个暂停功能，按 ESC 暂停

AI generates events JSON → Paste to: Existing event sheet
```

## Features

| Feature | Description |
|---------|-------------|
| Events | Game logic (movement, collision, scoring, AI, timers) |
| Objects | Sprite, Text, TiledBackground with behaviors |
| Layouts | Complete scenes (layers + instances + event sheet) |
| ImageData | Placeholder PNG base64 (colored shapes) |
| Validation | Verify JSON format before paste |

## Paste Locations

| Output Type | Paste To |
|-------------|----------|
| `layouts` | Project Bar → Layouts |
| `object-types` | Project Bar → Object types |
| `events` | Event sheet margin |
| `world-instances` | Layout view |

## Limitations

- ❌ Does NOT generate .c3p project files
- ❌ Does NOT generate production art (placeholder shapes only)
- ❌ Construct 3 only (no other engines)

## Project Structure

```
Construct3-Copilot/
├── .claude/
│   └── skills/
│       └── construct3-copilot/    # Claude Code Skill
│           ├── SKILL.md           # Execution instructions
│           ├── CLAUDE.md          # Behavior constraints
│           ├── references/        # Reference docs
│           └── scripts/           # Helper scripts
├── data/
│   └── schemas/                   # ACE Schema (72 plugins + 31 behaviors)
└── tests/
    └── examples/                  # JSON examples (breakout, platformer)
```

### ACE Schema

Generated from `source/zh-CN_R466.csv` via `scripts/generate-schema.js`:

```
data/schemas/
├── index.json          # Summary index
├── plugins/            # 72 plugins (677 conditions, 776 actions, 957 expressions)
├── behaviors/          # 31 behaviors (115 conditions, 248 actions, 138 expressions)
├── effects/            # 89 effects
└── editor/             # Editor configuration
```

**Statistics**: 2,911 ACE (792 conditions + 1,024 actions + 1,095 expressions)

## License

[MIT](LICENSE)
