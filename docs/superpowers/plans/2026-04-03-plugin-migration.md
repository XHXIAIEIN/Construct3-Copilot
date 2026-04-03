# Plugin Architecture Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate construct3-copilot from a single skill (`.claude/skills/`) to a Claude Code plugin (`.claude/plugins/`) with 4 specialized skills sharing common scripts and references.

**Architecture:** Move entire directory to `.claude/plugins/construct3-copilot/`, add `plugin.json`, split current SKILL.md into 4 focused skills under `skills/{create,validate,addon,search}/SKILL.md`. Scripts, references, CLAUDE.md, and assets stay at plugin root unchanged. Update all external path references (CI, tests, copilot-instructions).

**Tech Stack:** Claude Code plugin system, Python 3.11+ scripts, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-04-03-plugin-architecture-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `.claude/plugins/construct3-copilot/plugin.json` | Plugin manifest declaring 4 skills |
| Create | `.claude/plugins/construct3-copilot/skills/create/SKILL.md` | Generate event sheets, layouts, objects |
| Create | `.claude/plugins/construct3-copilot/skills/validate/SKILL.md` | Validate + debug clipboard JSON |
| Create | `.claude/plugins/construct3-copilot/skills/addon/SKILL.md` | Addon SDK development guidance |
| Create | `.claude/plugins/construct3-copilot/skills/search/SKILL.md` | ACE query + documentation search |
| Move | `scripts/`, `references/`, `CLAUDE.md`, `assets/` | Shared infrastructure at plugin root |
| Archive | `.claude/skills/construct3-copilot/` | → `.trash/skill-monolith-2026-04-03/` |
| Update | `tests/test_service_integration.py` | Script paths |
| Update | `.github/workflows/validate-agents-skill.yml` | Trigger paths + script paths |
| Update | `.github/copilot-instructions.md` | Documentation paths |

---

### Task 1: Move directory and create plugin.json

**Files:**
- Move: `.claude/skills/construct3-copilot/` → `.claude/plugins/construct3-copilot/`
- Create: `.claude/plugins/construct3-copilot/plugin.json`
- Create: `.claude/plugins/construct3-copilot/skills/create/` (empty dir)
- Create: `.claude/plugins/construct3-copilot/skills/validate/` (empty dir)
- Create: `.claude/plugins/construct3-copilot/skills/addon/` (empty dir)
- Create: `.claude/plugins/construct3-copilot/skills/search/` (empty dir)
- Delete: `.claude/skills/construct3-copilot/SKILL.md` (old monolith SKILL.md — content goes into 4 new files in Task 2-5)

- [ ] **Step 1: Create plugin directory and move files**

```bash
mkdir -p .claude/plugins
# Git mv preserves history
git mv .claude/skills/construct3-copilot .claude/plugins/construct3-copilot
# Create skill subdirectories
mkdir -p .claude/plugins/construct3-copilot/skills/create
mkdir -p .claude/plugins/construct3-copilot/skills/validate
mkdir -p .claude/plugins/construct3-copilot/skills/addon
mkdir -p .claude/plugins/construct3-copilot/skills/search
```

- [ ] **Step 2: Remove old monolith SKILL.md**

The old SKILL.md at `.claude/plugins/construct3-copilot/SKILL.md` contains the combined skill — it will be replaced by 4 individual SKILL.md files in Tasks 2-5. Archive it:

```bash
mv .claude/plugins/construct3-copilot/SKILL.md .trash/skill-monolith-2026-04-03-SKILL.md
```

- [ ] **Step 3: Create plugin.json**

Write to `.claude/plugins/construct3-copilot/plugin.json`:

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

- [ ] **Step 4: Verify directory structure**

```bash
find .claude/plugins/construct3-copilot -maxdepth 3 -type f | head -20
```

Expected: plugin.json at root, CLAUDE.md at root, scripts/ and references/ intact, 4 empty skills/ subdirs.

- [ ] **Step 5: Commit**

```bash
git add .claude/plugins/ .claude/skills/
git commit -m "refactor: move construct3-copilot from skill to plugin structure"
```

---

### Task 2: Write create/SKILL.md

**Files:**
- Create: `.claude/plugins/construct3-copilot/skills/create/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write to `.claude/plugins/construct3-copilot/skills/create/SKILL.md`:

```markdown
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

# 2. Usage patterns
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}

# 3. Generate
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

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/instructions.md |
| JSON format | @${CLAUDE_PLUGIN_ROOT}/references/clipboard-format.md |
| Behavior IDs | @${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md |
| Object templates | @${CLAUDE_PLUGIN_ROOT}/references/object-templates.md |
| Layout templates | @${CLAUDE_PLUGIN_ROOT}/references/layout-templates.md |
| End-to-end examples | @${CLAUDE_PLUGIN_ROOT}/references/examples.md |
| Prompt templates | @${CLAUDE_PLUGIN_ROOT}/references/prompts.md |
| Chinese terms | @${CLAUDE_PLUGIN_ROOT}/references/zh-cn.md |
| Family patterns | @${CLAUDE_PLUGIN_ROOT}/references/family-patterns.md |
| Effects/shaders | @${CLAUDE_PLUGIN_ROOT}/references/effects-guide.md |

## Boundaries

- Output: Construct 3 clipboard JSON only (events, object-types, layouts, world-instances, event-sheets)
- Images: Placeholder geometric shapes only — no pixel art, no AI art
- Engine: Construct 3 only
- Validation: must pass validate/output.py before delivery
```

- [ ] **Step 2: Commit**

```bash
git add .claude/plugins/construct3-copilot/skills/create/SKILL.md
git commit -m "feat: add create skill — generate C3 clipboard JSON"
```

---

### Task 3: Write validate/SKILL.md

**Files:**
- Create: `.claude/plugins/construct3-copilot/skills/validate/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write to `.claude/plugins/construct3-copilot/skills/validate/SKILL.md`:

```markdown
name: c3-validate
description: >
  Validate Construct 3 clipboard JSON for structural correctness, identify errors, suggest fixes,
  and repair broken JSON. Debug paste failures in the C3 editor.
  验证 Construct 3 剪贴板 JSON 的结构正确性，诊断粘贴错误，修复损坏的 JSON。
triggers:
  keywords:
    - validate clipboard
    - check json
    - verify json
    - paste error
    - parse error
    - fix json
    - repair json
    - debug paste
    - clipboard error
    - 检查
    - 验证
    - 粘贴报错
    - 修复
  intents:
    - validate_c3_json
    - debug_paste_error
---

# Validate — Check and Repair Construct 3 JSON

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` for known hallucination traps and format rules.

## Workflow

1. Run local validation:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate/output.py '{json}'
```

2. When Clipboard service is online, also run:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'
```

3. For ACE ID verification:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}
```

## References

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/clipboard-format.md |
| Paste errors | @${CLAUDE_PLUGIN_ROOT}/references/troubleshooting.md |
| Behavior IDs | @${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md |

## Output Format

```
Errors: [list of structural/semantic errors with line-level detail]
Warnings: [list of non-blocking issues]
Fixed JSON: [if repairable, the corrected clipboard JSON]
Fix summary: [what was changed and why]
```

## Boundaries

- Does NOT generate new content from scratch (use c3-create for that)
- CAN modify/repair existing JSON to fix errors
- Accepts JSON from clipboard, file, or inline string
```

- [ ] **Step 2: Commit**

```bash
git add .claude/plugins/construct3-copilot/skills/validate/SKILL.md
git commit -m "feat: add validate skill — check and repair C3 JSON"
```

---

### Task 4: Write addon/SKILL.md

**Files:**
- Create: `.claude/plugins/construct3-copilot/skills/addon/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write to `.claude/plugins/construct3-copilot/skills/addon/SKILL.md`:

```markdown
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

## Boundaries

- Addon SDK v2 only (not v1)
- Does NOT generate clipboard JSON (use c3-create)
- Does NOT validate clipboard JSON (use c3-validate)
- Outputs: addon file structure + JavaScript/TypeScript code + aces.json + lang files
```

- [ ] **Step 2: Commit**

```bash
git add .claude/plugins/construct3-copilot/skills/addon/SKILL.md
git commit -m "feat: add addon skill — Addon SDK v2 development guidance"
```

---

### Task 5: Write search/SKILL.md

**Files:**
- Create: `.claude/plugins/construct3-copilot/skills/search/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write to `.claude/plugins/construct3-copilot/skills/search/SKILL.md`:

```markdown
name: c3-search
description: >
  Search Construct 3 ACE definitions, explain plugin/behavior capabilities, and find
  real-world usage patterns from 403 official example projects.
  搜索 Construct 3 ACE 定义，解释插件/行为功能，查找官方示例项目中的实际用法。
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

# Real-world usage patterns
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py condition {ace_id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py top actions 20
```

## References

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/behavior-names.md |
| Chinese queries | @${CLAUDE_PLUGIN_ROOT}/references/zh-cn.md |

## Boundaries

- Read-only — does NOT generate clipboard JSON (use c3-create)
- Does NOT modify any files
- Returns ACE definitions, parameters, usage examples, and explanations
```

- [ ] **Step 2: Commit**

```bash
git add .claude/plugins/construct3-copilot/skills/search/SKILL.md
git commit -m "feat: add search skill — ACE query and documentation"
```

---

### Task 6: Update external path references

**Files:**
- Modify: `tests/test_service_integration.py`
- Modify: `.github/workflows/validate-agents-skill.yml`
- Modify: `.github/copilot-instructions.md`

- [ ] **Step 1: Update test script paths**

In `tests/test_service_integration.py`, replace the SCRIPTS constant:

```python
# Old:
SCRIPTS = ".claude/skills/construct3-copilot/scripts"

# New:
SCRIPTS = ".claude/plugins/construct3-copilot/scripts"
```

This is a single string replacement. All tests use this constant for script paths.

- [ ] **Step 2: Run tests to verify paths work**

```bash
python -m pytest tests/test_service_integration.py -v
```

Expected: 26 passed

- [ ] **Step 3: Update CI workflow**

In `.github/workflows/validate-agents-skill.yml`, replace all occurrences:

```yaml
# Trigger paths:
- ".claude/plugins/**"     # was: ".claude/skills/**"

# Script paths in steps:
python .claude/plugins/construct3-copilot/scripts/query/schema.py search collision
python .claude/plugins/construct3-copilot/scripts/validate/output.py tests/fixtures/events_basic.json
python .claude/plugins/construct3-copilot/scripts/infra/health.py --brief
python .claude/plugins/construct3-copilot/scripts/query/rag.py search collision || true
python .claude/plugins/construct3-copilot/scripts/generate/clipboard_service.py health || true

# Frontmatter validation:
p = Path(".claude/plugins/construct3-copilot/skills/create/SKILL.md")
```

- [ ] **Step 4: Update copilot-instructions.md**

In `.github/copilot-instructions.md`, replace all `.claude/skills/` with `.claude/plugins/`:

```markdown
- `.claude/plugins/construct3-copilot/skills/create/SKILL.md` — main generation skill
- `.claude/plugins/construct3-copilot/CLAUDE.md` — constraints and hallucination traps
```

- [ ] **Step 5: Run tests again**

```bash
python -m pytest tests/test_service_integration.py -v
```

Expected: 26 passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_service_integration.py .github/workflows/validate-agents-skill.yml .github/copilot-instructions.md
git commit -m "refactor: update all paths from .claude/skills/ to .claude/plugins/"
```

---

### Task 7: Final verification and cleanup

**Files:**
- Archive: `.trash/skill-monolith-2026-04-03-SKILL.md`
- Verify: all plugin files

- [ ] **Step 1: Verify plugin structure**

```bash
find .claude/plugins/construct3-copilot -type f | sort
```

Expected output (key files):
```
.claude/plugins/construct3-copilot/CLAUDE.md
.claude/plugins/construct3-copilot/assets/evaluations.json
.claude/plugins/construct3-copilot/plugin.json
.claude/plugins/construct3-copilot/references/addon-sdk-index.md
.claude/plugins/construct3-copilot/references/behavior-names.md
.claude/plugins/construct3-copilot/references/clipboard-format.md
...
.claude/plugins/construct3-copilot/scripts/infra/health.py
.claude/plugins/construct3-copilot/scripts/query/rag.py
.claude/plugins/construct3-copilot/scripts/query/schema.py
...
.claude/plugins/construct3-copilot/skills/addon/SKILL.md
.claude/plugins/construct3-copilot/skills/create/SKILL.md
.claude/plugins/construct3-copilot/skills/search/SKILL.md
.claude/plugins/construct3-copilot/skills/validate/SKILL.md
```

- [ ] **Step 2: Verify old skill directory is gone**

```bash
ls .claude/skills/construct3-copilot 2>/dev/null && echo "ERROR: old dir still exists" || echo "OK: old dir removed"
```

Expected: `OK: old dir removed`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/test_service_integration.py -v
```

Expected: 26 passed

- [ ] **Step 4: Verify each SKILL.md has valid frontmatter**

```bash
for skill in create validate addon search; do
  python -c "
import re
from pathlib import Path
p = Path('.claude/plugins/construct3-copilot/skills/$skill/SKILL.md')
text = p.read_text(encoding='utf-8')
m = re.match(r'^(.*?)\n---\n', text, flags=re.S)
assert m, f'$skill: missing frontmatter'
fm = m.group(1)
assert 'name:' in fm, f'$skill: missing name'
assert 'description:' in fm, f'$skill: missing description'
print(f'$skill: OK')
"
done
```

Expected: all 4 print OK

- [ ] **Step 5: Commit cleanup + plan**

```bash
git add .trash/ docs/superpowers/plans/2026-04-03-plugin-migration.md
git commit -m "chore: archive old monolith SKILL.md + add migration plan"
```
