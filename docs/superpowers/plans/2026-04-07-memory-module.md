# Memory Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement persistent cross-session memory for C3 Copilot via hook-driven extraction — no new scripts, no external deps.

**Architecture:** Pure hook-driven. Stop hook (prompt type) tells Claude to extract and write memory. SessionStart hook loads both profile and project context. CLAUDE.md already documents all rules — hooks just enforce execution.

**Tech Stack:** Claude Code plugin hooks (prompt type), bash (welcome.sh enhancement)

---

## Current State

- `CLAUDE.md`: Full memory rules documented (entry format, extract/skip rules, privacy, archive rotation)
- `memory/profile.md`: Exists, empty (header only)
- `memory/archive/.gitkeep`: Archive directory exists
- `welcome.sh`: Reads profile.md, does NOT load project memory
- All 4 SKILL.md files: Have "Memory Context" section (instruction to load project memory on trigger)
- `plugin.json`: Only has SessionStart hook, **no Stop hook**

## What Needs to Be Built

1. **Stop hook** — prompt-based, instructs Claude to extract and persist memory
2. **welcome.sh enhancement** — scan for `.c3proj`, load project memory into SessionStart output

---

### Task 1: Add Stop Hook to plugin.json

**Files:**
- Modify: `.claude/plugins/construct3-copilot/plugin.json`

The Stop hook uses `type: "prompt"` — Claude receives the prompt at session end and follows it to extract/write memory. No shell scripts needed.

- [ ] **Step 1: Add Stop hook with memory extraction prompt**

In `plugin.json`, add a `Stop` hook array alongside the existing `SessionStart`:

```json
{
  "name": "construct3-copilot",
  "version": "2.1.0",
  "description": "Construct 3 game development assistant — generates clipboard JSON, validates output, guides addon development, and searches ACE documentation",
  "skills": [
    "skills/c3-create",
    "skills/c3-validate",
    "skills/c3-addon",
    "skills/c3-search"
  ],
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/infra/welcome.sh\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Before ending this session, extract and persist memory per the rules in ${CLAUDE_PLUGIN_ROOT}/CLAUDE.md § Memory Management.\n\n## Steps\n\n1. Review the conversation for extractable information (skill level signals, project context, resolved problems, user preferences).\n2. Skip: operational Q&A, info already in project files, single-session debug details, Copilot errors.\n3. If nothing worth extracting → do nothing, stop here.\n4. Classify each piece as **profile** (user-level) or **project** (project-level).\n5. For profile entries → read `${CLAUDE_PLUGIN_ROOT}/memory/profile.md`. If entry count >= 20, append the oldest entries to `${CLAUDE_PLUGIN_ROOT}/memory/archive/profile-archived.md` (create if needed), then remove them from profile.md. Append new entries using the format: `### [Title]\\n[Content]\\n_Recorded YYYY-MM-DD_`\n6. For project entries → find `.c3proj` in the working directory tree, read its `uniqueId`. Target file: `{project_root}/.claude/memory/memory.md`. If it doesn't exist, create it with header `# Project Memory — {project name} (uniqueId: {id})`. Same overflow/archive rules — archive to `{project_root}/.claude/memory/archive/memory-archived.md`. Append new entries.\n7. No personal identity info. No verbatim quotes. Abstract only.\n8. Do not announce what you extracted to the user — just write silently."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify plugin.json is valid JSON**

Run: `python3 -c "import json; json.load(open('.claude/plugins/construct3-copilot/plugin.json')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/plugins/construct3-copilot/plugin.json
git commit -m "feat(memory): add Stop hook for automatic memory extraction"
```

---

### Task 2: Enhance welcome.sh to Load Project Memory

**Files:**
- Modify: `.claude/plugins/construct3-copilot/scripts/infra/welcome.sh`

Currently welcome.sh loads profile but not project memory. Add a section that searches for `.c3proj` and reads project memory if it exists.

- [ ] **Step 1: Add project memory loading after user profile section**

Insert the following block after the "User Profile" section (after `fi` on line 67) and before the "Instruction to Claude" section:

```bash
# 3b. Project memory (if .c3proj found)
C3PROJ=""
# Search current dir and one level up for .c3proj
for D in "$PROJECT_ROOT" "$PARENT_DIR"; do
  FOUND=$(find "$D" -maxdepth 1 -name "*.c3proj" -print -quit 2>/dev/null)
  if [ -n "$FOUND" ]; then
    C3PROJ="$FOUND"
    break
  fi
done

if [ -n "$C3PROJ" ]; then
  C3PROJ_DIR=$(dirname "$C3PROJ")
  PROJ_MEMORY="$C3PROJ_DIR/.claude/memory/memory.md"
  if [ -s "$PROJ_MEMORY" ]; then
    echo "## Project Memory"
    grep -v '^<!--' "$PROJ_MEMORY" | head -40
    echo ""
  fi
fi
```

- [ ] **Step 2: Update the SessionStart instruction to reference project memory**

Replace the instruction section to acknowledge project memory:

```bash
# 4. Instruction to Claude
echo "## SessionStart Instruction"
echo "用中文向用户打招呼。简短介绍当前服务状态，提示用户可以用哪些 skill。"
echo "如果有 User Profile，根据用户等级调整语气。"
echo "如果有 Project Memory，简要提及上次的项目进展。"
echo "不要逐字复读以上内容，用自然的方式表达。"
```

- [ ] **Step 3: Verify welcome.sh runs without errors**

Run: `bash .claude/plugins/construct3-copilot/scripts/infra/welcome.sh`
Expected: Output includes `=== Construct 3 Copilot ===` with services, skills, and instructions. No errors.

- [ ] **Step 4: Commit**

```bash
git add .claude/plugins/construct3-copilot/scripts/infra/welcome.sh
git commit -m "feat(memory): load project memory in SessionStart hook"
```

---

### Task 3: Verify End-to-End Integration

No new files — just verification that all pieces connect.

- [ ] **Step 1: Verify profile.md structure is ready**

Run: `cat .claude/plugins/construct3-copilot/memory/profile.md`
Expected: Header comments with entry format instructions. No entries yet (clean slate).

- [ ] **Step 2: Verify archive directory exists**

Run: `ls .claude/plugins/construct3-copilot/memory/archive/`
Expected: `.gitkeep` file present.

- [ ] **Step 3: Verify CLAUDE.md memory section matches implementation**

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` § Memory Management and cross-check:
- Entry format matches what Stop hook writes: `### [Title]\n[Content]\n_Recorded YYYY-MM-DD_` ✓
- Archive locations match: `profile-archived.md` and `memory-archived.md` ✓
- Max 20 entries rule referenced in Stop hook prompt ✓
- Extract/skip rules referenced in Stop hook prompt ✓

- [ ] **Step 4: Verify plugin.json hook structure is valid for Claude Code**

Run: `python3 -c "import json; d=json.load(open('.claude/plugins/construct3-copilot/plugin.json')); print('Hooks:', list(d['hooks'].keys()))"`
Expected: `Hooks: ['SessionStart', 'Stop']`
