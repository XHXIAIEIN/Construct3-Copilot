"""
Answer generation — the core Copilot pipeline.

Consumes RAG search results + LLM to produce answers.
"""
import logging
import time
from typing import Dict, List, Optional

from src.llm import LLMClient
from src.rag_client import RAGClient, SearchResponse
from .models import CopilotResponse
from .context import format_context_blocks, format_sources_summary
from .reflection import self_reflect
from .query import classify_query, is_complex_query, rewrite_query, decompose_query
from .prompts import (
    SYSTEM_MESSAGE,
    QA_PROMPT,
    STRICT_QA_PROMPT,
    LOW_RELEVANCE_PROMPT,
    NO_RESULTS_RESPONSE,
    LLM_UNAVAILABLE_RESPONSE,
    RAG_UNAVAILABLE_RESPONSE,
    LOW_CONFIDENCE_WARNING,
)

logger = logging.getLogger(__name__)


class AnswerPipeline:
    """
    Main answer generation pipeline.

    Flow: query → RAG search → context formatting → LLM generation → response
    """

    def __init__(self, llm: LLMClient, rag: RAGClient):
        self.llm = llm
        self.rag = rag

    def answer(self, query: str) -> CopilotResponse:
        """
        Auto-routing entry point.

        Classifies query type and dispatches to the appropriate handler.
        """
        query_type = classify_query(self.llm, query)

        if query_type == "code":
            return self.answer_code(query)
        return self.answer_smart(query)

    def answer_smart(self, query: str) -> CopilotResponse:
        """
        Recommended entry point: auto complexity detection + fallback.

        Simple queries → answer_qa
        Complex queries → answer_complex
        Service errors  → graceful fallback
        """
        if not self.rag.is_available():
            return CopilotResponse(
                answer=RAG_UNAVAILABLE_RESPONSE,
                sources=[],
                query_type="error",
                confidence="none",
            )

        if not self.llm.is_available:
            # RAG available but LLM not — return raw sources
            search_resp = self.rag.search(query)
            summary = format_sources_summary(search_resp.results)
            return CopilotResponse(
                answer=LLM_UNAVAILABLE_RESPONSE.format(sources_summary=summary),
                sources=[{"source": r.source} for r in search_resp.results],
                query_type="fallback",
                confidence="none",
                route=search_resp.route,
            )

        if is_complex_query(query):
            return self.answer_complex(query)
        return self.answer_qa(query)

    def answer_qa(
        self,
        query: str,
        use_strict_mode: bool = True,
    ) -> CopilotResponse:
        """Standard Q&A with anti-hallucination measures."""
        t0 = time.time()

        # Retrieve
        search_resp = self.rag.search(query)
        results = search_resp.results

        # Lookup hit — return directly
        if search_resp.route == "lookup" and results:
            return CopilotResponse(
                answer=results[0].text,
                sources=[{"source": "lookup"}],
                query_type="lookup",
                confidence="high",
                route="lookup",
            )

        # No results
        if not results:
            # Try query rewrite
            rewrites = rewrite_query(self.llm, query)
            for rq in rewrites[:2]:
                retry_resp = self.rag.search(rq, skip_lookup=True)
                if retry_resp.results:
                    results = retry_resp.results
                    break

            if not results:
                return CopilotResponse(
                    answer=NO_RESULTS_RESPONSE,
                    sources=[],
                    query_type="qa",
                    confidence="none",
                )

        # Format context
        context = format_context_blocks(results)

        # Generate answer
        if len(results) <= 2:
            prompt = LOW_RELEVANCE_PROMPT.format(
                result_count=len(results),
                context=context,
                question=query,
            )
        elif use_strict_mode:
            prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        else:
            prompt = QA_PROMPT.format(context=context, question=query)

        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        # Determine confidence based on result scores
        avg_score = sum(r.score for r in results) / len(results)
        if avg_score >= 0.7:
            confidence = "high"
        elif avg_score >= 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        if confidence == "low":
            answer = LOW_CONFIDENCE_WARNING + "\n\n" + answer

        sources = [{"source": r.source, "collection": r.collection} for r in results]

        return CopilotResponse(
            answer=answer,
            sources=sources,
            query_type="qa",
            confidence=confidence,
            route=search_resp.route,
        )

    def answer_high_confidence(self, query: str) -> CopilotResponse:
        """
        High-confidence Q&A: multi-query retrieval + self-reflection.

        Generates multiple search queries, fuses results,
        then verifies the answer via self-reflection.
        """
        # Multi-query retrieval
        rewrites = rewrite_query(self.llm, query)
        all_queries = [query] + rewrites[:2]

        all_results = []
        for q in all_queries:
            resp = self.rag.search(q, skip_lookup=True)
            all_results.extend(resp.results)

        # Deduplicate by source
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            key = r.text[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if not unique:
            return CopilotResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa",
                confidence="none",
            )

        # Generate with strict mode
        context = format_context_blocks(unique[:10])
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        # Self-reflection verification
        reflection, is_reliable = self_reflect(self.llm, query, answer, context)

        confidence = "high" if is_reliable else "low"
        if not is_reliable:
            answer = LOW_CONFIDENCE_WARNING + "\n\n" + answer

        return CopilotResponse(
            answer=answer,
            sources=[{"source": r.source} for r in unique[:10]],
            query_type="qa",
            confidence=confidence,
            verification_notes=reflection,
        )

    def answer_complex(self, query: str) -> CopilotResponse:
        """
        Complex multi-step query: decompose → search each → fuse → generate.
        """
        sub_queries = decompose_query(self.llm, query)
        if not sub_queries:
            return self.answer_qa(query)

        # Search each sub-query
        all_results = []
        for sq in sub_queries:
            resp = self.rag.search(sq, skip_lookup=True)
            all_results.extend(resp.results)

        # Also search original query
        original_resp = self.rag.search(query, skip_lookup=True)
        all_results.extend(original_resp.results)

        # Deduplicate
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            key = r.text[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if not unique:
            return CopilotResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa",
                confidence="none",
            )

        context = format_context_blocks(unique[:10])
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        return CopilotResponse(
            answer=answer,
            sources=[{"source": r.source} for r in unique[:10]],
            query_type="qa",
            confidence="medium",
        )

    def answer_stream(self, query: str):
        """Streaming answer generation (yields chunks)."""
        search_resp = self.rag.search(query)
        results = search_resp.results

        if search_resp.route == "lookup" and results:
            yield results[0].text
            return

        if not results:
            yield NO_RESULTS_RESPONSE
            return

        context = format_context_blocks(results)
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)

        yield from self.llm.generate_stream(prompt, system=SYSTEM_MESSAGE)

    def answer_code(self, query: str) -> CopilotResponse:
        """Generate Construct 3 clipboard JSON via schema-driven pipeline."""
        from .clipboard import EventGenerator, extract_json_from_response

        generator = EventGenerator()
        prompt = generator.build_prompt(query)
        llm_response = self.llm.generate(prompt, system=SYSTEM_MESSAGE)
        result = generator.process_response(llm_response)

        if result["success"]:
            answer = result["json"]
            confidence = "high"
        else:
            errors = "\n".join(result["errors"])
            answer = f"{llm_response}\n\nValidation errors:\n{errors}"
            confidence = "low"

        return CopilotResponse(
            answer=answer,
            sources=[],
            query_type="code",
            confidence=confidence,
        )

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Multi-turn chat with RAG context.

        Retrieves context based on the last user message,
        injects it into the system prompt, then generates.
        """
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            search_resp = self.rag.search(last_user_msg)
            context = format_context_blocks(search_resp.results)

            system_with_context = (
                f"{SYSTEM_MESSAGE}\n\n"
                f"## Verified reference materials\n{context}"
            )
            enhanced = [{"role": "system", "content": system_with_context}] + messages
            return self.llm.chat(enhanced)

        return self.llm.chat(messages)
