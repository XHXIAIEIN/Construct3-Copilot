#!/usr/bin/env bash
# C3 Copilot — SessionStart welcome script
# Outputs context for Claude to greet the user with project status.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
SCRIPTS="$PLUGIN_ROOT/scripts"

echo "=== Construct 3 Copilot ==="
echo ""

# 1. Service health (fast, --brief = one line)
echo "## Services"
if command -v python3 &>/dev/null; then
  python3 "$SCRIPTS/infra/health.py" --brief 2>/dev/null || echo "RAG:? Clipboard:?"
elif command -v python &>/dev/null; then
  python "$SCRIPTS/infra/health.py" --brief 2>/dev/null || echo "RAG:? Clipboard:?"
else
  echo "RAG:? Clipboard:? (python not found)"
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

# 4. Instruction to Claude
echo "## SessionStart Instruction"
echo "用中文向用户打招呼。简短介绍当前服务状态，提示用户可以用哪些 skill。"
echo "如果有 User Profile，根据用户等级调整语气。"
echo "不要逐字复读以上内容，用自然的方式表达。"
