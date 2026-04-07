# Construct 3 Copilot

[中文](README_CN.md) | **English**

Generate Construct 3 clipboard JSON from natural language and paste directly into the editor.

## Quick Start

```bash
# 1. Clone Copilot
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot

# 2. Auto-clone all dependencies + install pip packages
bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh

# 3. Start services (each in its own terminal)
cd ../Construct3-RAG && python src/api.py
cd ../Construct3-Clipboard && python src/api.py

# 4. Run Copilot
cd ../Construct3-Copilot && claude
```

> Requires [Claude Code CLI](https://claude.ai/download) and Python 3.10+

## Ecosystem

Copilot is a Claude Code plugin that depends on two sibling services:

**Services** (need startup):

| Repository | Role | Port |
|------------|------|------|
| [Construct3-Copilot](https://github.com/XHXIAIEIN/Construct3-Copilot) | Claude Code plugin (skills, scripts, orchestration) | — |
| [Construct3-RAG](https://github.com/XHXIAIEIN/Construct3-RAG) | ACE schema search + documentation retrieval | 8765 |
| [Construct3-Clipboard](https://github.com/XHXIAIEIN/Construct3-Clipboard) | Clipboard JSON generation + validation | 8766 |

**References** (read-only, used by skills):

| Repository | Used by |
|------------|---------|
| [Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | `/c3-addon` — official SDK templates |
| [Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | `/c3-search` — official game examples |
| [Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | `/c3-addon` — SDK documentation |

```
../
├── Construct3-Copilot/           ← Claude Code plugin (you are here)
├── Construct3-RAG/               ← ACE schema + docs service
├── Construct3-Clipboard/         ← JSON generation + validation service
├── Construct-Addon-SDK/          ← Official SDK templates (Scirra)
├── Construct-Example-Projects/   ← Official examples (Scirra)
└── Construct3-Manual/            ← SDK documentation
```

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
