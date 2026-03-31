"""
Construct 3 Copilot Configuration

Copilot is the generation layer — it consumes RAG's /search API
and uses LLM to produce answers, clipboard JSON, and evaluations.
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
DATA_DIR = BASE_DIR / "data"

# =============================================================================
# RAG Service (retrieval backend)
# =============================================================================
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8765")

# =============================================================================
# LLM Configuration
# =============================================================================
# provider=ollama:       LLM_MODEL=qwen2.5:7b
# provider=openai:       LLM_MODEL=moonshot-v1-128k / gpt-4o  (requires API Key)
# provider=huggingface:  LLM_MODEL=Qwen/Qwen3.5-9B             (local inference)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# =============================================================================
# Copilot API Server
# =============================================================================
COPILOT_PORT = int(os.getenv("COPILOT_PORT", "8766"))

# =============================================================================
# UI Language (for user-facing messages only)
# =============================================================================
UI_LANGUAGE: str = os.getenv("UI_LANGUAGE", "zh")
