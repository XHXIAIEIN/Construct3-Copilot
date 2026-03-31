"""
Copilot Core Configuration

Copilot Core is the orchestration service — it coordinates LLM calls,
session state, and downstream modules (RAG, Clipboard, MCP).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# Directory Structure
# =============================================================================
BASE_DIR = Path(__file__).parent.parent

# =============================================================================
# Copilot Core API Server
# =============================================================================
COPILOT_HOST = os.getenv("COPILOT_HOST", "0.0.0.0")
COPILOT_PORT = int(os.getenv("COPILOT_PORT", "8767"))

# =============================================================================
# LLM Configuration
# =============================================================================
# provider: "claude" | "openai" | "ollama"
#   claude  → model=claude-sonnet-4-20250514  (requires ANTHROPIC_API_KEY)
#   openai  → model=gpt-4o / deepseek-chat    (requires LLM_API_KEY)
#   ollama  → model=qwen2.5:7b                (local, no key)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")  # only needed for openai/ollama
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# =============================================================================
# Downstream Modules
# =============================================================================
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8765")
CLIPBOARD_API_URL = os.getenv("CLIPBOARD_API_URL", "http://localhost:8766")

# =============================================================================
# Session
# =============================================================================
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

# =============================================================================
# UI Language (for user-facing messages)
# =============================================================================
UI_LANGUAGE: str = os.getenv("UI_LANGUAGE", "zh")
