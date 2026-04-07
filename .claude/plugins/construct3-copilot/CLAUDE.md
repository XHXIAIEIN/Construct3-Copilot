# Construct 3 Copilot — Constraints

Generates paste-ready Construct 3 clipboard JSON. This file defines hard rules that override defaults.

---

## Mandatory ACE Retrieval

**Before using ANY ACE ID, confirm it exists via RAG. Never guess from training data.**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {keyword}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py lookup {ace-id} --plugin {name}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py list {plugin-or-behavior}
```

Use an ACE ID that RAG cannot find = instant failure.

## Known Hallucination Traps

| Wrong (does not exist) | Correct (actual ID) |
|------------------------|---------------------|
| `set-angle-toward-position` | `set-angle` + `angle(x1,y1,x2,y2)` expression |
| `move-toward` | MoveTo behavior or manual displacement |
| `EightDir` | `8Direction` (use display name for behaviorType) |
| `set-speed` (8Direction) | `set-max-speed` |
| `on-click` (no params) | `on-click` requires `mouse-button` parameter |
| `toggle-boolean` | `toggle-boolean-eventvar` |
| `compare-boolean` | `compare-boolean-eventvar` |
| `add-to` | `add-to-eventvar` |

## Mandatory Workflow

```
DISCOVER → QUERY → GENERATE → VALIDATE → FIX
```

0. **Discover**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/infra/health.py --brief` to check service availability
1. **Query**: `${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py` for every ACE ID (mandatory)
2. **Generate**: Pass intent to `${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py generate`
3. **Validate**: `${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate` — fail = do not deliver
4. **Fix**: On validation failure, fix and re-validate (loop step 3, max 3 retries)

## Pre-Output Checklist

Before delivering JSON, all items must pass:

- [ ] `"is-c3-clipboard-data": true` present
- [ ] All ACE IDs confirmed via RAG lookup (0 unverified IDs)
- [ ] Variables include `comment` field (can be `""`)
- [ ] String params use nested quotes: `"\"value\""`
- [ ] Behavior actions include `behaviorType` (display name, not behaviorId)
- [ ] Comparison operators are numbers: 0=eq, 1=neq, 2=lt, 3=lte, 4=gt, 5=gte
- [ ] Key codes are numbers: 32=Space, 87=W, 65=A, 37=Left, 39=Right
- [ ] `${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate` passed
- [ ] Paste location specified (Event sheet margin / Project Bar / Layout view)
- [ ] Manual verification step included ("After pasting, run layout and confirm X")

## Language-Aware ACE Output

When the conversation is in Chinese, **all ACE names shown to the user must use Chinese translations** (from zh-CN schema `list-name`). Internal ACE IDs in generated JSON remain English.

| Context | Example |
|---------|---------|
| Explaining to user (Chinese) | `键盘 > 按住按键 > 空格` |
| Generated clipboard JSON | `"type": "keyboard", "id": "key-is-down"` |

Lookup flow: `${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py search {keyword}` → output includes bilingual labels (中文 / English). If zh-CN is missing, fall back to English.

## Never Do

- Deliver JSON without running `${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate`
- Deliver JSON when validation reports errors
- Use an ACE ID not confirmed by schema lookup
- Omit paste instructions from output

---

## Memory Management

Persistent cross-session memory. Fully automatic — users never manage memory directly.

### Memory Layers

| Layer | Location | Lifecycle |
|-------|----------|-----------|
| User Profile (global) | `${CLAUDE_PLUGIN_ROOT}/memory/profile.md` | Long-term, rarely changes |
| Project Context (per-project) | `{project_root}/.claude/memory/memory.md` | Tied to project |
| Session Buffer | In-context only | Extracted at session end |

### Entry Format

```markdown
### [Brief title]
[Content — abstracted, not verbatim quotes]
_Recorded YYYY-MM-DD_
```

### Skill Level Codes

| Code | Signal |
|------|--------|
| L1 | Unfamiliar with event sheet concepts, needs step-by-step guidance |
| L2 | Can use basic plugins/behaviors, needs ACE lookup assistance |
| L3 | Familiar with event system, needs help with complex logic and optimization |
| L4 | Uses scripting/SDK, needs architecture-level discussion |

### What to Extract

**Profile (user-level):**
- Skill level → store as code only (`skill_level: L2`)
- Preferred response language and style
- Commonly used plugins/behaviors patterns

**Project context:**
- Project name (human-readable, from `.c3proj`) + `uniqueId` in header
- Current feature/module being worked on
- Existing objects, behaviors, event sheet structure
- Problems encountered and their final solutions

### What NOT to Extract

- Operational Q&A ("how to export", "what's the shortcut")
- Information already in project files
- Single-session debugging details
- Copilot's own errors (e.g., ACE hallucinations)

### Privacy

- No personal identity information (name, contact, accounts)
- No verbatim conversation quotes — only abstracted state
- Only information directly related to C3 development

### When to Write Memory

At session end or when a meaningful task completes:

1. Extract key information from the conversation
2. Classify each piece as user profile or project context
3. Check target file entry count:
   - If count >= 20, append oldest entries to the archive file, remove them from main file
   - Profile archive: `${CLAUDE_PLUGIN_ROOT}/memory/archive/profile-archived.md`
   - Project archive: `{project_root}/.claude/memory/archive/memory-archived.md`
4. Append new entries to the appropriate file
5. If files/directories do not exist, create them

### Project Identification

- Read `.c3proj` file in project root
- Use `uniqueId` field as stable project identifier (project names can change)
- Store human-readable project name in `memory.md` header
