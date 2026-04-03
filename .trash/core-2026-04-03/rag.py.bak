#!/usr/bin/env python3
"""
RAG Semantic Search for Construct 3 Documentation

Searches vectorized Construct 3 docs and knowledge base for relevant context.
Requires a vector database backend (not yet configured).

Usage:
    python rag.py "how to implement enemy AI patrol"
    python rag.py --top-k 5 "pathfinding behavior setup"
"""

import json
import sys


def search(query: str, top_k: int = 5) -> list[dict]:
    """Search the knowledge base for relevant documents.

    Returns list of {"text": ..., "source": ..., "score": ...} dicts.
    """
    # TODO: implement vector search backend
    # Options: ChromaDB local, Qdrant, or simple TF-IDF over markdown files
    return []


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: rag.py <query> [--top-k N]"}))
        sys.exit(1)

    top_k = 5
    args = sys.argv[1:]
    if "--top-k" in args:
        idx = args.index("--top-k")
        top_k = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    query = " ".join(args)
    results = search(query, top_k)

    if not results:
        print(json.dumps({"error": "RAG backend not configured", "suggestion": "Run infra/health.py to check setup"}))
        sys.exit(1)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
