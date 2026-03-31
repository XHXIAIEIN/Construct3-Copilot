"""
RAGAS-inspired evaluation metrics.

Embedding metrics (no LLM needed):
  - context_precision, context_recall, answer_correctness, answer_completeness

LLM-judge metrics:
  - faithfulness, answer_relevance
"""
from __future__ import annotations
import logging
from typing import List

import numpy as np

from src.benchmark import MetricResult

logger = logging.getLogger(__name__)

_METRIC_WEIGHTS = {
    "faithfulness":          0.20,
    "answer_relevance":      0.20,
    "answer_correctness":    0.20,
    "context_precision":     0.15,
    "context_recall":        0.10,
    "answer_completeness":   0.0,
}

_FAITHFULNESS_PROMPT = (
    "You are an evaluation assistant. Determine if the following answer "
    "is entirely based on the provided references with no fabricated information.\n\n"
    "References:\n{contexts}\n\n"
    "Answer:\n{answer}\n\n"
    "Reply ONLY: 1 (fully grounded) or 0 (contains information not in references)."
)

_RELEVANCE_PROMPT = (
    "You are an evaluation assistant. Rate how well the answer addresses the question.\n\n"
    "Question: {query}\n"
    "Answer: {answer}\n\n"
    "Output a score from 0.0 to 1.0 (1.0=perfectly on topic). Output only the number."
)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class RagasEvaluator:
    def __init__(self, embedder=None, llm=None):
        self._embedder = embedder
        self._llm = llm

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._embedder.encode(texts)
        return np.array(vecs)

    def _compute_context_precision(self, query: str, contexts: list[str], threshold: float = 0.4) -> float:
        if not contexts or self._embedder is None:
            return 0.0
        q_vec = self._embed([query])[0]
        c_vecs = self._embed(contexts)
        sims = [_cosine_similarity(q_vec, cv) for cv in c_vecs]
        return sum(1 for s in sims if s >= threshold) / len(contexts)

    def _compute_context_recall(self, contexts: list[str], ground_truth: str) -> float:
        if not ground_truth or not contexts or self._embedder is None:
            return 0.0
        gt_vec = self._embed([ground_truth])[0]
        c_vecs = self._embed(contexts)
        return min(1.0, max(_cosine_similarity(gt_vec, cv) for cv in c_vecs))

    def _compute_answer_correctness(self, answer: str, ground_truth: str) -> float:
        if not ground_truth or self._embedder is None:
            return 0.0
        a_vec = self._embed([answer])[0]
        gt_vec = self._embed([ground_truth])[0]
        return max(0.0, _cosine_similarity(a_vec, gt_vec))

    def _compute_faithfulness(self, answer: str, contexts: list[str]) -> float:
        if not self._llm or not contexts:
            return 0.0
        ctx_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts[:5]))
        prompt = _FAITHFULNESS_PROMPT.format(contexts=ctx_text, answer=answer[:800])
        try:
            out = self._llm.generate(prompt).strip()
            return 1.0 if out.startswith("1") else 0.0
        except Exception:
            logger.warning("Faithfulness LLM call failed", exc_info=True)
            return 0.0

    def _compute_answer_relevance(self, query: str, answer: str) -> float:
        if not self._llm:
            return 0.0
        prompt = _RELEVANCE_PROMPT.format(query=query, answer=answer[:800])
        try:
            out = self._llm.generate(prompt).strip()
            return min(1.0, max(0.0, float(out)))
        except (ValueError, Exception):
            logger.warning("Answer relevance LLM call failed", exc_info=True)
            return 0.0

    def evaluate(self, query: str, answer: str, contexts: list[str], ground_truth: str = "") -> List[MetricResult]:
        w = _METRIC_WEIGHTS
        return [
            MetricResult("faithfulness", self._compute_faithfulness(answer, contexts), w["faithfulness"]),
            MetricResult("answer_relevance", self._compute_answer_relevance(query, answer), w["answer_relevance"]),
            MetricResult("answer_correctness", self._compute_answer_correctness(answer, ground_truth), w["answer_correctness"]),
            MetricResult("context_precision", self._compute_context_precision(query, contexts), w["context_precision"]),
            MetricResult("context_recall", self._compute_context_recall(contexts, ground_truth), w["context_recall"]),
            MetricResult("answer_completeness", self._compute_answer_correctness(answer, ground_truth), 0.0),
        ]
