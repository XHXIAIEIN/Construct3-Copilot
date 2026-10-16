#!/usr/bin/env bash
# Construct 3 Copilot — dependency setup
# Clones sibling repos and installs pip dependencies.
#
# Usage:
#   bash setup.sh           # clone + install all
#   bash setup.sh --check   # check only, no changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# infra -> scripts -> construct3-copilot -> plugins -> .claude -> PROJECT_ROOT
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
if COMMON_DIR=$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
  CLONE_ROOT="$(cd "$COMMON_DIR/.." && pwd)"
else
  CLONE_ROOT="$PROJECT_ROOT"
fi
PARENT_DIR="$(cd "$CLONE_ROOT/.." && pwd)"

# --- Config ---

# Services: need clone + pip install + manual startup
SERVICE_REPOS=(
  "Construct3-RAG|https://github.com/XHXIAIEIN/Construct3-RAG.git"
  "Construct3-Clipboard|https://github.com/XHXIAIEIN/Construct3-Clipboard.git"
)

# References: clone only, no install needed
REFERENCE_REPOS=(
  "Construct3-Agent-Skills|https://github.com/XHXIAIEIN/Construct3-Agent-Skills.git"
  "Construct-Addon-SDK|https://github.com/Scirra/Construct-Addon-SDK.git"
  "Construct-Example-Projects|https://github.com/Scirra/Construct-Example-Projects.git"
  "Construct3-Manual|https://github.com/XHXIAIEIN/Construct3-Manual.git"
)

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
fi

# --- Functions ---
status_icon() {
  if [[ "$1" == "true" ]]; then echo "+"; else echo "-"; fi
}

check_repo() {
  local name="$1"
  local path="$PARENT_DIR/$name"
  if [[ -e "$path/.git" ]]; then
    echo "true"
  else
    echo "false"
  fi
}

clone_repo() {
  local name="$1"
  local url="$2"
  local path="$PARENT_DIR/$name"

  if [[ -e "$path/.git" ]]; then
    echo "  [skip] $name already exists"
    return 0
  fi

  echo "  [clone] $name → $path"
  git clone "$url" "$path"
}

install_deps() {
  local name="$1"
  local path="$PARENT_DIR/$name"
  local req="$path/requirements.txt"

  if [[ ! -f "$req" && -f "$path/src/requirements.txt" ]]; then
    req="$path/src/requirements.txt"
  fi

  if [[ ! -f "$req" ]]; then
    echo "  [skip] $name has no requirements.txt"
    return 0
  fi

  echo "  [pip] $req"
  python -m pip install -q -r "$req" 2>/dev/null || python3 -m pip install -q -r "$req" 2>/dev/null || {
    echo "  [warn] pip install failed for $name"
    return 0
  }
}

# --- Main ---
echo "=== Construct 3 Copilot Setup ==="
echo "Project: $PROJECT_ROOT"
echo "Sibling: $PARENT_DIR"
echo ""

# Check mode
if $CHECK_ONLY; then
  echo "## Services (need startup)"
  for entry in "${SERVICE_REPOS[@]}"; do
    IFS='|' read -r name url <<< "$entry"
    exists=$(check_repo "$name")
    echo "  $name: $(status_icon "$exists")"
  done
  echo ""
  echo "## References (read-only)"
  for entry in "${REFERENCE_REPOS[@]}"; do
    IFS='|' read -r name url <<< "$entry"
    exists=$(check_repo "$name")
    echo "  $name: $(status_icon "$exists")"
  done
  echo ""
  echo "## Python Packages"
  python -m pip check 2>/dev/null | head -5 || echo "  (pip check unavailable)"
  exit 0
fi

# Clone service repos
echo "## Cloning services..."
for entry in "${SERVICE_REPOS[@]}"; do
  IFS='|' read -r name url <<< "$entry"
  clone_repo "$name" "$url"
done
echo ""

# Clone reference repos
echo "## Cloning references..."
for entry in "${REFERENCE_REPOS[@]}"; do
  IFS='|' read -r name url <<< "$entry"
  clone_repo "$name" "$url"
done
echo ""

# Install pip deps for service repos + Copilot itself
echo "## Installing pip dependencies..."
install_deps "Construct3-Copilot"
for entry in "${SERVICE_REPOS[@]}"; do
  IFS='|' read -r name url <<< "$entry"
  install_deps "$name"
done
echo ""

echo "## Done"
echo "Next steps:"
echo "  1. Start RAG:       cd $PARENT_DIR/Construct3-RAG && python -m uvicorn src.api:app --host 127.0.0.1 --port 8765"
echo "  2. Start Clipboard: cd $PARENT_DIR/Construct3-Clipboard && python -m uvicorn src.api:app --host 127.0.0.1 --port 8766"
echo "  3. Run Copilot:     cd $PROJECT_ROOT && claude"
