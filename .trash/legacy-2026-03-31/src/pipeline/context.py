"""
Context formatting — transforms raw search results into
structured context blocks for LLM consumption.
"""
from typing import List, Set

from src.rag_client import SearchResult
from .prompts import SOURCE_LABEL


# Source collections grouped by semantic role
_ACE_COLLECTIONS = frozenset({"ace", "effects"})
_DOC_COLLECTIONS = frozenset({"guide", "interface", "project", "plugins", "behaviors", "scripting"})
_TERM_COLLECTIONS = frozenset({"terms"})
_EXAMPLE_COLLECTIONS = frozenset({"examples"})

_CONTEXT_GROUPS: list[tuple[frozenset, str, str]] = [
    (_ACE_COLLECTIONS, "ACE Reference",
     "Actions, Conditions, and Expressions available in the Construct 3 editor:"),
    (_DOC_COLLECTIONS, "Documentation",
     "Relevant sections from the Construct 3 manual:"),
    (_TERM_COLLECTIONS, "Terminology", ""),
    (_EXAMPLE_COLLECTIONS, "Examples", ""),
]

_CONTEXT_CHAR_BUDGET = 8000
_DEDUP_THRESHOLD = 0.70


def format_single_result(result: SearchResult, idx: int) -> str:
    """Format one search result as a numbered context block."""
    source = result.source
    heading = result.metadata.get("h2_heading", "")
    section = result.metadata.get("section_type", "")

    header_parts = [f"[{idx}]"]
    if source:
        header_parts.append(source)
    if heading:
        header_parts.append(f"> {heading}")
    if section:
        header_parts.append(f"[{section}]")

    header = " ".join(header_parts)
    return f"{header}\n{result.text}\n{SOURCE_LABEL}: {source}"


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """Remove near-duplicate results via Jaccard word-overlap."""
    if len(results) <= 1:
        return results

    unique: List[SearchResult] = []
    seen_words: List[Set[str]] = []

    for r in results:
        words = set(r.text.split())
        is_dup = False
        for sw in seen_words:
            if not words or not sw:
                continue
            overlap = len(words & sw) / max(len(words | sw), 1)
            if overlap > _DEDUP_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            unique.append(r)
            seen_words.append(words)

    return unique


def format_context_blocks(results: List[SearchResult]) -> str:
    """
    Format search results into grouped, numbered context blocks.

    Groups results by collection type (ACE, docs, terms, examples),
    deduplicates, and enforces a character budget.
    """
    results = deduplicate_results(results)

    grouped: dict[str, list[tuple[SearchResult, int]]] = {}
    for idx, r in enumerate(results, 1):
        coll = r.collection
        for source_set, group_name, _ in _CONTEXT_GROUPS:
            if coll in source_set:
                grouped.setdefault(group_name, []).append((r, idx))
                break
        else:
            grouped.setdefault("Other", []).append((r, idx))

    blocks: list[str] = []
    total_chars = 0

    for source_set, group_name, description in _CONTEXT_GROUPS:
        items = grouped.get(group_name, [])
        if not items:
            continue

        section_parts = [f"## {group_name}"]
        if description:
            section_parts.append(description)

        for r, idx in items:
            block = format_single_result(r, idx)
            if total_chars + len(block) > _CONTEXT_CHAR_BUDGET:
                break
            section_parts.append(block)
            total_chars += len(block)

        blocks.append("\n\n".join(section_parts))

    return "\n\n---\n\n".join(blocks)


def format_sources_summary(results: List[SearchResult]) -> str:
    """Readable summary of sources for fallback responses."""
    if not results:
        return "(no sources available)"

    lines = []
    for i, r in enumerate(results[:5], 1):
        source = r.source or r.collection
        preview = r.text[:100].replace("\n", " ")
        lines.append(f"{i}. [{source}] {preview}...")

    return "\n".join(lines)
