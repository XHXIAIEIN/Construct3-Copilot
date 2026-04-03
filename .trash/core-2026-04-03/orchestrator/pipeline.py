"""Orchestration pipeline — the core of Copilot.

Dual-track pipeline:
- Q&A track: RAG-augmented LLM chat (Phase 1.1, unchanged)
- JSON track: clipboard JSON detection → validate → RAG → LLM → output validate

Phase 2: adds JSON processing track.
"""
import logging

from src.llm.client import LLMClient
from src.llm.prompts.system import COPILOT_SYSTEM
from src.llm.prompts.clipboard import build_clipboard_prompt
from src.modules.rag_client import RAGClient
from src.orchestrator.session import SessionManager
from src.orchestrator.router import decide_delivery
from src.orchestrator.detector import detect_clipboard_json, DetectionResult
from src.orchestrator.validator import validate_local
from src.orchestrator.json_extract import extract_clipboard_json_from_reply
from src.schemas.api import ChatRequest, ChatResponse, GenerationData
from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


class Pipeline:
    """Main orchestration pipeline."""

    def __init__(self, llm: LLMClient, sessions: SessionManager, rag: RAGClient = None):
        self.llm = llm
        self.sessions = sessions
        self.rag = rag

    # ── Shared helpers ──────────────────────────────────────────────────

    async def _fetch_rag_context(self, query: str) -> tuple[str, bool]:
        """Search RAG for relevant C3 knowledge. Returns (context_str, used)."""
        if not self.rag:
            return "", False
        try:
            if not await self.rag.is_available():
                return "", False
            resp = await self.rag.search(query, top_k=5)
            if not resp.results:
                return "", False
            chunks = []
            for r in resp.results:
                chunks.append(f"[{r.collection}] (score: {r.score:.2f})\n{r.text}")
            context = "\n\n---\n\n".join(chunks)
            logger.info(f"RAG returned {len(resp.results)} results (route: {resp.route})")
            return context, True
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return "", False

    def _build_system_prompt(self, rag_context: str) -> str:
        """Build system prompt for Q&A track, optionally augmented with RAG results."""
        if not rag_context:
            return COPILOT_SYSTEM
        return (
            COPILOT_SYSTEM
            + "\n\n## Reference Knowledge (from RAG)\n\n"
            "The following are relevant Construct 3 documentation and examples "
            "retrieved for this conversation. Use them to give accurate, specific answers. "
            "If the retrieved content conflicts with your training data, prefer the retrieved content.\n\n"
            + rag_context
        )

    # ── Main entry ──────────────────────────────────────────────────────

    async def process(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request through the pipeline."""
        # [1] Session
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        # Append user message
        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        # [2] JSON detection
        detection = detect_clipboard_json(request.message)

        if detection.found:
            return await self._process_json(session, detection)
        else:
            return await self._process_qa(session, request)

    # ── Q&A track (Phase 1.1, unchanged) ────────────────────────────────

    async def _process_qa(self, session: SessionState, request: ChatRequest) -> ChatResponse:
        """Q&A track: RAG-augmented LLM chat."""
        modules_used = []

        rag_context, rag_used = await self._fetch_rag_context(request.message)
        if rag_used:
            modules_used.append("rag")

        try:
            system_prompt = self._build_system_prompt(rag_context)
            messages = [
                {"role": "system", "content": system_prompt},
                *session.messages,
            ]
            reply = await self.llm.chat(messages)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ChatResponse(
                session_id=session.session_id,
                type="error",
                message=f"LLM error: {e}",
            )

        session.messages.append({"role": "assistant", "content": reply})
        session.touch()

        delivery = decide_delivery(session)
        logger.debug(f"Route decision: {delivery}")

        return ChatResponse(
            session_id=session.session_id,
            type="direct_answer",
            message=reply,
            modules_used=modules_used,
        )

    # ── JSON processing track (Phase 2) ─────────────────────────────────

    def _build_rag_query_from_json(self, clipboard_json: dict) -> str:
        """Extract searchable terms from clipboard JSON for RAG query."""
        terms = set()
        items = clipboard_json.get("items", [])
        for item in items:
            if not isinstance(item, dict):
                continue
            for node_list_key in ("conditions", "actions"):
                for node in item.get(node_list_key, []):
                    if isinstance(node, dict):
                        if oc := node.get("objectClass"):
                            terms.add(oc)
                        if bt := node.get("behaviorType"):
                            terms.add(bt)
                        if aid := node.get("id"):
                            terms.add(aid)
            if pid := item.get("plugin-id"):
                terms.add(pid)
            for beh in item.get("behaviorTypes", []):
                if isinstance(beh, dict) and (bid := beh.get("behaviorId")):
                    terms.add(bid)
            for child in item.get("children", []):
                if isinstance(child, dict):
                    for key in ("conditions", "actions"):
                        for node in child.get(key, []):
                            if isinstance(node, dict):
                                if oc := node.get("objectClass"):
                                    terms.add(oc)
                                if bt := node.get("behaviorType"):
                                    terms.add(bt)

        if not terms:
            return f"Construct 3 clipboard {clipboard_json.get('type', 'events')} format"
        return " ".join(sorted(terms))

    async def _process_json(self, session: SessionState, detection: DetectionResult) -> ChatResponse:
        """JSON processing track: validate → RAG → LLM → output validate."""
        modules_used = []

        # [4] Local validation
        input_report = validate_local(detection.clipboard_json)

        # [5] RAG retrieval
        rag_query = self._build_rag_query_from_json(detection.clipboard_json)
        rag_context, rag_used = await self._fetch_rag_context(rag_query)
        if rag_used:
            modules_used.append("rag")

        # [6-7] LLM call with clipboard-specific prompt
        try:
            system_prompt = build_clipboard_prompt(
                clipboard_json=detection.clipboard_json,
                validation_report=input_report,
                rag_context=rag_context,
                user_instruction=detection.user_instruction,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                *session.messages,
            ]
            reply = await self.llm.chat(messages)
            modules_used.append("llm")
        except Exception as e:
            logger.error(f"LLM call failed in JSON track: {e}")
            return ChatResponse(
                session_id=session.session_id,
                type="direct_answer" if input_report.passed else "error",
                message=self._format_validation_fallback(input_report),
                data=GenerationData(
                    delivery="clipboard",
                    input_validation=input_report.to_dict(),
                ),
                modules_used=modules_used,
            )

        session.messages.append({"role": "assistant", "content": reply})
        session.touch()

        # [8] Extract and validate output JSON
        output_json = extract_clipboard_json_from_reply(reply)
        output_validation = None
        if output_json:
            output_report = validate_local(output_json)
            output_validation = output_report.to_dict()

        # [9] Deliver
        if output_json:
            return ChatResponse(
                session_id=session.session_id,
                type="generation",
                message=reply,
                data=GenerationData(
                    delivery="clipboard",
                    clipboard_json=output_json,
                    validation=output_validation,
                    input_validation=input_report.to_dict(),
                ),
                modules_used=modules_used,
            )
        else:
            return ChatResponse(
                session_id=session.session_id,
                type="direct_answer",
                message=reply,
                data=GenerationData(
                    delivery="clipboard",
                    input_validation=input_report.to_dict(),
                ) if input_report.issues else None,
                modules_used=modules_used,
            )

    def _format_validation_fallback(self, report) -> str:
        """Format validation report as human-readable text (LLM fallback)."""
        if report.passed and not report.issues:
            return "JSON validation passed. No issues found. (LLM unavailable for further analysis)"
        lines = ["JSON validation results (LLM unavailable):", ""]
        for issue in report.issues:
            prefix = "ERROR" if issue.level == "error" else "WARNING"
            loc = f" at {issue.path}" if issue.path else ""
            lines.append(f"  [{prefix}] {issue.message}{loc}")
        return "\n".join(lines)

    # ── Streaming ───────────────────────────────────────────────────────

    async def process_stream(self, request: ChatRequest):
        """Streaming version — yields SSE-formatted chunks.

        Note: JSON track does not support streaming in Phase 2.
        If clipboard JSON is detected, falls back to non-streaming process().
        """
        detection = detect_clipboard_json(request.message)
        if detection.found:
            response = await self.process(request)
            import json
            yield f"data: {json.dumps(response.model_dump(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Q&A track: stream as before
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        rag_context, _ = await self._fetch_rag_context(request.message)
        system_prompt = self._build_system_prompt(rag_context)

        messages = [
            {"role": "system", "content": system_prompt},
            *session.messages,
        ]

        full_reply = []
        async for token in self.llm.stream(messages):
            full_reply.append(token)
            yield f"data: {token}\n\n"

        complete = "".join(full_reply)
        session.messages.append({"role": "assistant", "content": complete})
        session.touch()

        yield "data: [DONE]\n\n"
