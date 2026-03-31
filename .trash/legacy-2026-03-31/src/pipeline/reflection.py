"""
Self-Reflection — verifies LLM answers against source materials.

Asks the LLM to check its own answer for hallucinations,
unsupported claims, and citation accuracy.
"""
import logging

from src.llm import LLMClient
from .prompts import (
    SELF_REFLECTION_PROMPT,
    REFLECTION_VERDICT_KEY,
    REFLECTION_UNRELIABLE,
    REFLECTION_RELIABLE,
)

logger = logging.getLogger(__name__)


def self_reflect(
    llm: LLMClient,
    query: str,
    answer: str,
    context: str,
) -> tuple[str, bool]:
    """
    Verify answer reliability against source context.

    Returns:
        (reflection_text, is_reliable)
    """
    prompt = SELF_REFLECTION_PROMPT.format(
        context=context,
        question=query,
        answer=answer,
    )
    reflection = llm.generate(prompt)

    # Parse verdict from reflection output
    is_reliable = _parse_verdict(reflection)
    return reflection, is_reliable


def _parse_verdict(reflection: str) -> bool:
    """Parse the reliability verdict from reflection text.

    Scans for the verdict line containing REFLECTION_VERDICT_KEY,
    then checks for UNRELIABLE before RELIABLE (since "Reliable"
    is a substring of "Unreliable").
    """
    for line in reflection.splitlines():
        if REFLECTION_VERDICT_KEY not in line:
            continue
        if REFLECTION_UNRELIABLE in line:
            return False
        if REFLECTION_RELIABLE in line:
            return True

    # Default to reliable if no verdict found
    return True
