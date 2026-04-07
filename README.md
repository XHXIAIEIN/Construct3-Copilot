# Construct 3 Copilot

[中文](README_CN.md) | **English**

Generate Construct 3 clipboard JSON from natural language and paste directly into the editor.

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
> Create a breakout game, paddle follows mouse

AI generates:
- layout.json  → Paste to: Project Bar → Layouts
- events.json  → Paste to: Event sheet margin
```

**Add Feature**
```
> Add WASD 8-direction movement controls

AI generates events JSON → Paste to: Event sheet margin
```

**UI Snippet**
```
> Add a pause feature, press ESC to pause

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

## Skills

This project works as a [Claude Code Plugin](https://docs.anthropic.com/en/docs/claude-code/plugins). Four skills are available:

| Skill | Description |
|-------|-------------|
| `/c3-create` | Generate clipboard JSON from natural language |
| `/c3-search` | Query ACE docs + search Construct 3 documentation |
| `/c3-validate` | Validate / fix clipboard JSON |
| `/c3-addon` | Addon SDK v2 development guidance |

## Paste Locations

| Output Type | Paste To |
|-------------|----------|
| `layouts` | Project Bar → Layouts |
| `object-types` | Project Bar → Object types |
| `events` | Event sheet margin |
| `world-instances` | Layout view |

## Limitations

- Does not generate `.c3p` project files
- Does not generate production art (placeholder shapes only)
- Construct 3 only (no other engines)

## Project Structure

```
Construct3-Copilot/
├── .claude/
│   └── plugins/
│       └── construct3-copilot/       # Claude Code Plugin
│           ├── plugin.json
│           ├── CLAUDE.md
│           ├── skills/               # 4 skills (c3-create, c3-search, c3-validate, c3-addon)
│           └── scripts/              # RAG query, clipboard service, image generation
├── docs/                             # Design specs & references
├── tests/
│   ├── examples/                     # Full game examples (breakout, platformer)
│   ├── fixtures/                     # Minimal JSON fixtures (validation)
│   └── regressions/                  # Regression test cases
└── plans/                            # Implementation plans
```

## License

[MIT](LICENSE)
