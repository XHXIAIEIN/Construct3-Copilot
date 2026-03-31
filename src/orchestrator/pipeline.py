"""Orchestration pipeline — the core of Copilot.

Workflow: Intent → Clarify → Refine → Route → Execute → Deliver

Phase 1.1: RAG-augmented LLM chat. RAG results are injected into the
system prompt so the LLM has real C3 plugin/behavior data to work with.
"""
import logging

from src.llm.client import LLMClient
from src.llm.prompts.system import COPILOT_SYSTEM
from src.modules.rag_client import RAGClient
from src.orchestrator.session import SessionManager
from src.orchestrator.router import decide_delivery
from src.schemas.api import ChatRequest, ChatResponse, GenerationData
from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


class Pipeline:
    """Main orchestration pipeline."""

    def __init__(self, llm: LLMClient, sessions: SessionManager, rag: RAGClient = None):
        self.llm = llm
        self.sessions = sessions
        self.rag = rag

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
        """Build system prompt, optionally augmented with RAG results."""
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

        modules_used = []

        # [2] RAG retrieval
        rag_context, rag_used = await self._fetch_rag_context(request.message)
        if rag_used:
            modules_used.append("rag")

        # [3] LLM call with RAG-augmented context
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

        # Append assistant reply
        session.messages.append({"role": "assistant", "content": reply})
        session.touch()

        # [5] Route decision (logged but not acted on in Phase 1)
        delivery = decide_delivery(session)
        logger.debug(f"Route decision: {delivery} (not executed in Phase 1)")

        return ChatResponse(
            session_id=session.session_id,
            type="direct_answer",
            message=reply,
            modules_used=modules_used,
        )

    async def process_stream(self, request: ChatRequest):
        """Streaming version — yields SSE-formatted chunks."""
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        # RAG retrieval for stream too
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
