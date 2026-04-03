# Construct 3 Copilot Plugin Architecture Design

**Date**: 2026-04-03
**Status**: Draft
**Supersedes**: Single-skill architecture (`.claude/skills/construct3-copilot/`)

---

## 1. Goal

Transform the Construct 3 Copilot from a single monolithic skill into a Claude Code plugin with 4 specialized skills. Each skill loads only its required context, shares a common scripts/ and references/ layer, and can leverage external services (RAG :8765, Clipboard :8766) via HTTP bridge scripts.

## 2. Design Principles

- **Per-intent skill routing**: Skills split by user intent (create / validate / addon / search), not by technical function
- **Shared infrastructure**: scripts/ and references/ are common to all skills, referenced via `${CLAUDE_PLUGIN_ROOT}`
- **Progressive disclosure**: Each SKILL.md is <80 lines, loads only the references it needs
- **Zero-change service layer**: Existing scripts (health.py, rag.py, clipboard_service.py, schema.py, validate/output.py) are reused unchanged
- **Graceful degradation**: All 4 skills work offline (RAG/Clipboard down), with reduced capability

## 3. Plugin Structure

```
.claude/plugins/construct3-copilot/
├── plugin.json                         ← Plugin manifest
├── CLAUDE.md                           ← Global constraints (hallucination traps, validation rules)
│
├── skills/
│   ├── create/SKILL.md                 ← Generate event sheets, layouts, objects
│   ├── validate/SKILL.md              ← Validate + debug clipboard JSON
│   ├── addon/SKILL.md                 ← Addon SDK development guidance
│   └── search/SKILL.md               ← ACE query + documentation search
│
├── scripts/                            ← Shared tools (UNCHANGED from current)
│   ├── infra/
│   │   └── health.py                  ← Service discovery
│   ├── query/
│   │   ├── schema.py                  ← Local ACE lookup
│   │   ├── rag.py                     ← RAG :8765 bridge
│   │   └── examples.py               ← Official project usage mining
│   ├── generate/
│   │   ├── imagedata.py               ← Placeholder PNG generation
│   │   ├── layout.py                  ← Layout presets
│   │   ├── clipboard.py              ← Local IR→JSON (scaffold)
│   │   └── clipboard_service.py      ← Clipboard :8766 bridge
│   └── validate/
│       └── output.py                  ← Local JSON validation
│
└── references/                         ← Shared knowledge base (UNCHANGED)
    ├── clipboard-format.md
    ├── behavior-names.md
    ├── object-templates.md
    ├── layout-templates.md
    ├── examples.md
    ├── instructions.md
    ├── prompts.md
    ├── troubleshooting.md
    ├── zh-cn.md
    ├── effects-guide.md
    ├── family-patterns.md
    ├── runtime-api.md
    ├── addon-sdk-index.md
    ├── addon-sdk/guide/
    ├── addon-sdk/reference/
    ├── copilot-system-prompt.md        ← Archive
    └── clipboard-system-prompt.md      ← Archive
```

## 4. plugin.json

```json
{
  "name": "construct3-copilot",
  "version": "2.0.0",
  "description": "Construct 3 game development assistant — generates clipboard JSON, validates output, guides addon development, and searches ACE documentation",
  "skills": [
    "skills/create",
    "skills/validate",
    "skills/addon",
    "skills/search"
  ]
}
```

## 5. Skill Specifications

### 5.1 create — Generate Game Content

**Identity**: Generates paste-ready Construct 3 clipboard JSON (event sheets, objects, layouts) from natural language game descriptions.

**Triggers**:
- Keywords: construct 3, c3, event sheet, platformer, shooter, breakout, tower defense, 平台游戏, 射击游戏, 做一个游戏, create game, generate events, game logic, spawn, bullet, collision, movement, scoring, inventory, dialogue system
- Intents: generate_c3_json, paste_to_c3, create_event_sheet, create_game_logic

**References loaded**:
- `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` (mandatory — constraints)
- `${CLAUDE_PLUGIN_ROOT}/references/instructions.md` (workflow)
- `${CLAUDE_PLUGIN_ROOT}/references/prompts.md` (templates)
- `${CLAUDE_PLUGIN_ROOT}/references/clipboard-format.md` (JSON format)
- `${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md` (ID mapping)
- `${CLAUDE_PLUGIN_ROOT}/references/object-templates.md` (object templates)
- `${CLAUDE_PLUGIN_ROOT}/references/layout-templates.md` (layout templates)
- `${CLAUDE_PLUGIN_ROOT}/references/examples.md` (end-to-end samples)
- `${CLAUDE_PLUGIN_ROOT}/references/zh-cn.md` (Chinese terms)

**Workflow**: DISCOVER → QUERY → GENERATE → VALIDATE → FIX (full pipeline from CLAUDE.md)

**Scripts used**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/infra/health.py --brief
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py search {keyword}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}       # when RAG online
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/imagedata.py --color {c} --width {W} --height {H}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/layout.py --preset {p}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py generate '{ir}'  # when Clipboard online
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate/output.py '{json}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'  # when Clipboard online
```

**Boundaries**:
- Output: Construct 3 clipboard JSON only
- Images: Placeholder geometric shapes only
- Engine: Construct 3 only
- Validation: must pass validate/output.py before delivery

---

### 5.2 validate — Validate and Debug

**Identity**: Validates Construct 3 clipboard JSON for structural correctness, identifies errors, suggests fixes, and repairs broken JSON.

**Triggers**:
- Keywords: validate, check json, verify clipboard, paste error, parse error, 检查, 验证, 粘贴报错, fix json, repair, debug paste
- Intents: validate_c3_json, debug_paste_error

**References loaded**:
- `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` (constraints)
- `${CLAUDE_PLUGIN_ROOT}/references/clipboard-format.md` (format rules)
- `${CLAUDE_PLUGIN_ROOT}/references/troubleshooting.md` (common errors)
- `${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md` (ID mapping)

**Workflow**:
1. Run `validate/output.py` on input JSON
2. If Clipboard service online, also run `clipboard_service.py validate`
3. Report errors with line-level detail
4. If repairable, output fixed JSON + explanation of changes

**Scripts used**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate/output.py '{json}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'  # when online
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}  # verify specific ACE IDs
```

**Boundaries**:
- Does NOT generate new content from scratch (use create for that)
- Can modify/repair existing JSON
- Accepts JSON from clipboard, file, or inline

---

### 5.3 addon — Addon SDK Development

**Identity**: Guides development of custom Construct 3 plugins and behaviors using the Addon SDK v2.

**Triggers**:
- Keywords: addon sdk, custom plugin, custom behavior, write plugin, write behavior, aces.json, addon.json, editor scripts, runtime scripts, c3runtime, 插件开发, 自定义行为
- Intents: develop_addon, create_plugin, create_behavior

**References loaded**:
- `${CLAUDE_PLUGIN_ROOT}/references/addon-sdk-index.md` (quick reference)
- `${CLAUDE_PLUGIN_ROOT}/references/addon-sdk/guide/` (all guide files)
- `${CLAUDE_PLUGIN_ROOT}/references/addon-sdk/reference/` (all API reference files)
- `${CLAUDE_PLUGIN_ROOT}/references/runtime-api.md` (scripting API)

**Workflow**:
1. Identify addon type (plugin vs behavior vs effect)
2. If RAG online, search for relevant documentation and examples
3. Generate file structure + code following SDK v2 patterns
4. Include aces.json, lang/en-US.json, c3runtime/ scripts

**Scripts used**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}  # when RAG online
```

**Boundaries**:
- Addon SDK v2 only (not v1)
- Does NOT generate clipboard JSON (use create for that)
- Does NOT validate clipboard JSON (use validate for that)

---

### 5.4 search — ACE Query and Documentation

**Identity**: Searches Construct 3 ACE definitions, explains plugin/behavior capabilities, and finds real-world usage patterns.

**Triggers**:
- Keywords: search ace, what actions, what conditions, list expressions, explain behavior, how to use, ACE 查询, 有哪些动作, 怎么用, plugin capabilities, find action
- Intents: search_ace, explain_plugin, find_usage

**References loaded**:
- `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` (hallucination traps — critical for search results)
- `${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md` (ID mapping)
- `${CLAUDE_PLUGIN_ROOT}/references/zh-cn.md` (Chinese terms)

**Workflow**:
1. Run `schema.py` for exact match
2. If RAG online, also run `rag.py` for semantic search + examples
3. Run `examples.py` for real-world usage patterns
4. Present results: ACE list + parameters + usage examples

**Scripts used**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py search {keyword}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {plugin}        # when RAG online
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {query}       # when RAG online
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}
```

**Boundaries**:
- Read-only — does NOT generate clipboard JSON
- Does NOT modify any files
- Returns information, not executable output

## 6. Trigger Disambiguation

Overlap risk between create and search (both respond to ACE-related queries).

**Resolution**: Description wording forces intent matching:
- create: "**Generates** paste-ready Construct 3 clipboard JSON from natural language **game descriptions**"
- search: "**Searches** Construct 3 ACE **definitions** and **explains** plugin capabilities"

Key signal words:
- "做/创建/生成/build/create/make" → create
- "查/搜/列出/explain/search/list/what does" → search
- "检查/验证/报错/fix/validate/error" → validate
- "插件开发/addon/SDK/custom behavior" → addon

## 7. Migration Plan

### Step 1: Create plugin directory structure
```bash
mkdir -p .claude/plugins/construct3-copilot/skills/{create,validate,addon,search}
```

### Step 2: Move files
```bash
# Move shared infrastructure
mv .claude/skills/construct3-copilot/scripts/ .claude/plugins/construct3-copilot/scripts/
mv .claude/skills/construct3-copilot/references/ .claude/plugins/construct3-copilot/references/
mv .claude/skills/construct3-copilot/CLAUDE.md .claude/plugins/construct3-copilot/CLAUDE.md
```

### Step 3: Create new files
- `plugin.json` — manifest
- `skills/create/SKILL.md` — from current SKILL.md (rewritten, focused on generation)
- `skills/validate/SKILL.md` — new
- `skills/addon/SKILL.md` — new
- `skills/search/SKILL.md` — new

### Step 4: Archive old skill
```bash
mv .claude/skills/construct3-copilot/ .trash/skill-monolith-2026-04-03/
```

### Step 5: Update external references
- `.github/copilot-instructions.md` — update paths
- `.github/workflows/validate-agents-skill.yml` — update paths
- `tests/test_service_integration.py` — update script paths

### Step 6: Verify
- Claude Code discovers all 4 skills via plugin
- Each skill triggers on correct keywords (manual test)
- All 26 integration tests pass with updated paths
- CI workflow passes

## 8. Degradation Matrix (unchanged)

| RAG | Clipboard | Effect |
|-----|-----------|--------|
| online | online | Full: semantic search + service generation + dual validation |
| online | offline | RAG enriches context, Claude generates, local validation only |
| offline | online | Local schema only, Clipboard generates + validates |
| offline | offline | Current behavior: local schema + Claude generates + local validation |

All skills work in all 4 states. Services enhance quality but are never required.

## 9. Files Changed Summary

| Action | File |
|--------|------|
| New | `.claude/plugins/construct3-copilot/plugin.json` |
| New | `.claude/plugins/construct3-copilot/skills/create/SKILL.md` |
| New | `.claude/plugins/construct3-copilot/skills/validate/SKILL.md` |
| New | `.claude/plugins/construct3-copilot/skills/addon/SKILL.md` |
| New | `.claude/plugins/construct3-copilot/skills/search/SKILL.md` |
| Move | `scripts/` → `.claude/plugins/.../scripts/` |
| Move | `references/` → `.claude/plugins/.../references/` |
| Move | `CLAUDE.md` → `.claude/plugins/.../CLAUDE.md` |
| Archive | `.claude/skills/construct3-copilot/` → `.trash/` |
| Update | `.github/copilot-instructions.md` (paths) |
| Update | `.github/workflows/validate-agents-skill.yml` (paths) |
| Update | `tests/test_service_integration.py` (script paths) |
