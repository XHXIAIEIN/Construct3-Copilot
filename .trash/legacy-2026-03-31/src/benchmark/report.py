"""Markdown report generation for benchmark results."""
from __future__ import annotations
from typing import List

from src.benchmark import EvalResult


def generate_report(results: List[EvalResult], mode: str = "all") -> str:
    if not results:
        return "# No evaluation results\n"

    total = len(results)
    avg_composite = sum(r.composite_score for r in results) / total
    avg_latency = sum(r.latency_ms for r in results) / total

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        grade_counts[r.grade] += 1

    weighted_names: list[str] = []
    seen: set[str] = set()
    for r in results:
        for m in r.metrics:
            if m.weight > 0 and m.name not in seen:
                weighted_names.append(m.name)
                seen.add(m.name)

    lines = [
        "# Construct 3 Copilot Benchmark Report",
        "",
        f"**Mode**: `{mode}` | **Cases**: {total} | "
        f"**Avg Latency**: {avg_latency:.0f}ms",
        "",
        "## Overall Scores",
        "",
        "| Metric | Avg Score | Weight |",
        "|--------|-----------|--------|",
    ]

    for name in weighted_names:
        scores, weight = [], 0.0
        for r in results:
            m = next((m for m in r.metrics if m.name == name), None)
            if m:
                scores.append(m.score)
                weight = m.weight
        if scores:
            avg = sum(scores) / len(scores)
            lines.append(f"| {name} | {avg:.2f} | {weight:.0%} |")

    lines += [
        f"| **Composite** | **{avg_composite:.2f}** | — |",
        "",
        f"Grade distribution: A={grade_counts['A']} B={grade_counts['B']} "
        f"C={grade_counts['C']} D={grade_counts['D']}",
        "",
        "## Per-Case Results",
        "",
        "| ID | Composite | Grade | Latency(ms) |",
        "|----|-----------|-------|-------------|",
    ]

    for r in results:
        lines.append(f"| {r.query_id} | {r.composite_score:.2f} | {r.grade} | {r.latency_ms:.0f} |")

    return "\n".join(lines)
