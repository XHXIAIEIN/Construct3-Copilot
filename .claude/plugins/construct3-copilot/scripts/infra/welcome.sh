#!/usr/bin/env bash
# C3 Copilot — SessionStart welcome script
# Outputs context for Claude to greet the user with project status.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
SCRIPTS="$PLUGIN_ROOT/scripts"

# construct3-copilot -> plugins -> .claude -> PROJECT_ROOT
PROJECT_ROOT="$(cd "$PLUGIN_ROOT/../../.." && pwd)"
PARENT_DIR="$(cd "$PROJECT_ROOT/.." && pwd)"

echo "=== Construct 3 Copilot ==="
echo ""

# 1. Service health (fast, --brief = one line)
echo "## Services"
if command -v python3 &>/dev/null; then
  HEALTH=$(python3 "$SCRIPTS/infra/health.py" --brief 2>/dev/null || echo "RAG:? Clipboard:?")
elif command -v python &>/dev/null; then
  HEALTH=$(python "$SCRIPTS/infra/health.py" --brief 2>/dev/null || echo "RAG:? Clipboard:?")
else
  HEALTH="RAG:? Clipboard:? (python not found)"
fi
echo "$HEALTH"

# 1b. Check if dependency repos are missing (services = required, references = optional)
MISSING_SVC=""
MISSING_REF=""
for REPO in Construct3-RAG Construct3-Clipboard; do
  if ! [ -d "$PARENT_DIR/$REPO/.git" ]; then
    MISSING_SVC="$MISSING_SVC $REPO"
  fi
done
for REPO in Construct-Addon-SDK Construct3-Manual; do
  if ! [ -d "$PARENT_DIR/$REPO/.git" ]; then
    MISSING_REF="$MISSING_REF $REPO"
  fi
done
if [ -n "$MISSING_SVC" ] || [ -n "$MISSING_REF" ]; then
  echo ""
  echo "## Missing Dependencies"
  if [ -n "$MISSING_SVC" ]; then
    echo "Services (required):$MISSING_SVC"
  fi
  if [ -n "$MISSING_REF" ]; then
    echo "References (optional):$MISSING_REF"
  fi
  echo "Run: bash $SCRIPTS/infra/setup.sh"
fi
echo ""

# 2. Available skills
echo "## Skills"
echo "- c3-create   — 生成 Construct 3 clipboard JSON"
echo "- c3-validate — 验证/修复 clipboard JSON"
echo "- c3-addon    — Addon SDK v2 开发"
echo "- c3-search   — ACE 查询 + 文档搜索"
echo ""

# 3. User profile (if exists)
PROFILE="$PLUGIN_ROOT/memory/profile.md"
if [ -s "$PROFILE" ]; then
  echo "## User Profile"
  # Skip comment lines and header, output content entries only
  grep -v '^<!--' "$PROFILE" | grep -v '^# ' | grep -v '^$' | head -20
  echo ""
fi

# 3b. Project memory (if .c3proj found)
C3PROJ=""
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

# 4. Instruction to Claude
echo "## SessionStart Instruction"
echo "用中文向用户打招呼。简短介绍当前服务状态，提示用户可以用哪些 skill。"
echo "如果有 User Profile，根据用户等级调整语气。"
echo "如果有 Project Memory，简要提及上次的项目进展。"
echo "不要逐字复读以上内容，用自然的方式表达。"
