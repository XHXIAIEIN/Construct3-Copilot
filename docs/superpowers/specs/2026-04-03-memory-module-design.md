# C3 Copilot Memory Module — Design Spec

## Goal

Provide persistent cross-session memory for C3 Copilot end users, so the Copilot recognizes returning users and retains context about their projects. Users do not manage memory — extraction and writing are fully automatic.

## Architecture

Pure hook-driven. No additional scripts or dependencies. Claude Code performs all extraction, classification, and file I/O within existing hook mechanisms.

## Memory Layers

### Layer 1: User Profile (global)

- **Location:** `.claude/memory/profile.md` (within the plugin directory scope, shared across all projects)
- **Content:**
  - Skill level: `L1` (beginner), `L2` (basic), `L3` (proficient), `L4` (advanced)
  - Preferred response language and style
  - Commonly used plugins/behaviors patterns
- **Capacity:** Max 20 entries. Overflow → archive.
- **Lifecycle:** Long-term, rarely changes.

### Layer 2: Project Context (per-project)

- **Location:** `{project_root}/.claude/memory/memory.md`
- **Header:** Records `.c3proj` `uniqueId` for identity verification.
- **Content:**
  - Project name (human-readable, from `.c3proj`)
  - Current feature/module being worked on
  - Existing objects, behaviors, event sheet structure
  - Problems encountered and how they were resolved
- **Capacity:** Max 20 entries. Overflow → archive.
- **Lifecycle:** Tied to project. Archived when project goes inactive.

### Layer 3: Session Buffer (ephemeral)

- **Location:** Not persisted. Exists only in conversation context.
- **Content:** Current conversation focus, recent decisions, temporary state.
- **Lifecycle:** At session end (`Stop` hook), Claude extracts key information and writes it to Layer 1 or Layer 2. Buffer then disappears.

## Archive

- **Profile archive:** `.claude/memory/archive/profile-archived.md`
- **Project archive:** `{project_root}/.claude/memory/archive/memory-archived.md`
- Contains original text of entries evicted from main files.
- Never loaded into context.

## Entry Format

Each entry in a memory file follows this format:

```markdown
### [Brief title]
[Content — abstract, not verbatim quotes]
_Recorded YYYY-MM-DD_
```

Timestamp is used for age-based eviction. When entry count exceeds 20, the oldest entries are appended to the archive file and removed from the main file.

## Hook Design

### SessionStart Hook

- Read `.claude/memory/profile.md` and inject into context.
- If file does not exist, skip (first-time user).

### Skill Trigger (in each SKILL.md)

- Locate `.c3proj` in project root, read `uniqueId`.
- Read `{project_root}/.claude/memory/memory.md` and inject into context.
- If file does not exist, skip (first time using this project with Copilot).

### Stop Hook

- Extract key information from the current conversation.
- Classify each piece as user profile or project context.
- Write to the corresponding file.
- Before writing, check entry count:
  1. If count >= 20, append oldest entries to archive file.
  2. Remove archived entries from main file.
  3. Write new entries.
- If files/directories do not exist, create them automatically.

## Extraction Rules

### Extract

- Skill level signals → store as level code only (`skill_level: L2`)
- Response style and language preferences
- Current project focus and progress
- Objects, behaviors, event sheet structures in use
- Problems and their final solutions

### Do Not Extract

- Operational Q&A ("how to export", "what's the shortcut")
- Information already in project files (no duplication)
- Single-session debugging details
- Copilot's own errors (e.g., ACE hallucinations)

## Privacy

- No personal identity information (name, contact, accounts).
- No verbatim conversation quotes — only abstracted preferences and project state.
- Only information directly related to C3 development.

## Project Identification

- Read `.c3proj` file in project root.
- Use `uniqueId` field as the stable project identifier (project names can change).
- Store human-readable project name inside `memory.md` header for readability.

## Skill Level Definitions

| Level | Signal |
|-------|--------|
| L1 Beginner | Unfamiliar with event sheet concepts, needs step-by-step guidance |
| L2 Basic | Can use basic plugins/behaviors, needs ACE lookup assistance |
| L3 Proficient | Familiar with event system, needs help with complex logic and optimization |
| L4 Advanced | Uses scripting/SDK, needs architecture-level discussion |

Only the level code is stored. Inference basis is not recorded.

## Integration Points

- `plugin.json`: Add hooks configuration.
- Each `SKILL.md`: Add one line to load project context on trigger.
- No new scripts required.
- No external dependencies.
