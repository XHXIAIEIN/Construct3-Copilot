from __future__ import annotations
import re
from typing import List

from src.benchmark import MetricResult
from src.pipeline.models import CopilotResponse

_WEIGHTS = {
    "instruction_following": 0.10,
    "citation_rate":         0.03,
    "confidence_quality":    0.02,
    "keyword_coverage":      0.0,
    "latency_ms":            0.0,
    "lookup_hit":            0.0,
    "collection_contribution": 0.0,
}

_NO_ANSWER_SIGNALS = ["not found", "no relevant", "cannot", "unknown", "未找到", "未提及", "无法"]
_CITATION_PATTERN = re.compile(
    r'\[Source[:：]\s*[\d,\s]+\]'
    r'|Source[:：]\s*\[\d+\]'
    r'|\[Source[:：]\s*\d+'
    r'|\[来源[:：]\s*[\d,\s]+\]'
    r'|来源[:：]\s*\[\d+\]'
    r'|参考资料\s*[\[【]\s*\d+'
)


def _score_keywords(answer: str, expected_keywords: list, has_answer: bool) -> float:
    if not expected_keywords:
        if not has_answer:
            hits = sum(1 for s in _NO_ANSWER_SIGNALS if s in answer.lower())
            return min(1.0, hits / 2)
        return 0.5
    lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in lower)
    return hits / len(expected_keywords)


def _score_citations(answer: str, has_answer: bool) -> float:
    if not has_answer:
        return 1.0 if any(s in answer.lower() for s in _NO_ANSWER_SIGNALS) else 0.3
    citations = _CITATION_PATTERN.findall(answer)
    if len(citations) >= 3:
        return 1.0
    elif len(citations) >= 1:
        return 0.6
    return 0.0


def _score_confidence(confidence: str) -> float:
    return {"high": 1.0, "medium": 0.6, "low": 0.3,
            "none": 0.0, "unknown": 0.0}.get(confidence, 0.0)


def _score_instruction_following(answer: str, confidence: str, has_answer: bool) -> float:
    citation_ok = _score_citations(answer, has_answer) >= 0.6
    confidence_ok = confidence in ("high", "medium", "low")
    return (0.7 if citation_ok else 0.0) + (0.3 if confidence_ok else 0.0)


class HeuristicEvaluator:
    def evaluate(
        self,
        query: str,
        response: CopilotResponse,
        expected_keywords: list,
        has_answer: bool = True,
        latency_ms: float = 0.0,
    ) -> List[MetricResult]:
        answer = response.answer
        confidence = response.confidence

        return [
            MetricResult("instruction_following",
                         _score_instruction_following(answer, confidence, has_answer),
                         _WEIGHTS["instruction_following"]),
            MetricResult("citation_rate",
                         _score_citations(answer, has_answer),
                         _WEIGHTS["citation_rate"]),
            MetricResult("confidence_quality",
                         _score_confidence(confidence),
                         _WEIGHTS["confidence_quality"]),
            MetricResult("keyword_coverage",
                         _score_keywords(answer, expected_keywords, has_answer),
                         0.0, {"expected": expected_keywords}),
            MetricResult("latency_ms", 0.0, 0.0, {"ms": latency_ms}),
        ]
