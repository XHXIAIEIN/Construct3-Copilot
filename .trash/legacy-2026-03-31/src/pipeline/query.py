"""
Query analysis and classification.

Determines query type, complexity, and generates
rewritten/decomposed queries for better retrieval.
"""
import re
import logging
from typing import List

from src.llm import LLMClient
from .prompts import ROUTER_PROMPT, QUERY_REWRITE_PROMPT, QUERY_DECOMPOSITION_PROMPT

logger = logging.getLogger(__name__)

# Keywords indicating a complex multi-step query
_COMPLEXITY_INDICATORS = [
    "并且", "同时", "然后", "步骤", "流程", "实现", "怎么做",
    "and", "then", "step", "workflow", "implement", "how to",
]

# Keywords indicating code/clipboard generation intent
_CODE_KEYWORDS = [
    "生成", "创建事件", "事件表", "JSON", "剪贴板",
    "generate", "create event", "clipboard", "event sheet",
]


def classify_query(llm: LLMClient, query: str) -> str:
    """Classify query as 'qa', 'code', or 'other'."""
    # Fast path: keyword detection
    query_lower = query.lower()
    for kw in _CODE_KEYWORDS:
        if kw in query_lower:
            return "code"

    # LLM classification
    prompt = ROUTER_PROMPT.format(query=query)
    result = llm.generate(prompt).strip().lower()
    if result in ("qa", "code", "other"):
        return result
    return "qa"


def is_complex_query(query: str) -> bool:
    """Detect if a query benefits from decomposition."""
    query_lower = query.lower()
    indicator_count = sum(1 for ind in _COMPLEXITY_INDICATORS if ind in query_lower)
    return indicator_count >= 2 or len(query) > 100


def rewrite_query(llm: LLMClient, query: str) -> List[str]:
    """Generate alternative search queries for better retrieval."""
    prompt = QUERY_REWRITE_PROMPT.format(query=query)
    result = llm.generate(prompt)
    return [line.strip() for line in result.strip().splitlines() if line.strip()]


def decompose_query(llm: LLMClient, query: str) -> List[str]:
    """Break a complex query into simpler sub-questions."""
    prompt = QUERY_DECOMPOSITION_PROMPT.format(query=query)
    result = llm.generate(prompt)
    sub_queries = [line.strip() for line in result.strip().splitlines() if line.strip()]
    return sub_queries[:4]  # cap at 4


def is_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r"[\u4e00-\u9fff]", text))
