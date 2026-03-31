"""Orchestration pipeline — the core of Copilot.

Workflow: Intent → Clarify → Refine → Route → Execute → Deliver

This is the Phase 1 skeleton — each stage has a working interface but
minimal implementation. Full pipeline logic comes in Phase 2.
"""
import logging

from src.llm.client import LLMClient
from src.llm.prompts.system import COPILOT_SYSTEM
from src.orchestrator.session import SessionManager
from src.orchestrator.router import decide_delivery
from src.schemas.api import ChatRequest, ChatResponse, GenerationData
from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


class Pipeline:
    """Main orchestration pipeline."""

    def __init__(self, llm: LLMClient, sessions: SessionManager):
        self.llm = llm
        self.sessions = sessions

    async def process(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request through the full pipeline.

        Phase 1 implementation: direct LLM chat (no RAG/Clipboard integration).
        The pipeline stages are stubbed for Phase 2 expansion.
        """
        # [1] Session
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        # Append user message
        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        # [2-4] Intent → Clarify → Refine (Phase 1: direct LLM pass-through)
        try:
            messages = [
                {"role": "system", "content": COPILOT_SYSTEM},
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
        )

    async def process_stream(self, request: ChatRequest):
        """Streaming version — yields SSE-formatted chunks.

        Phase 1 implementation: streams LLM tokens directly.
        """
        session = self.sessions.get_or_create(
            request.session_id,
            has_local_project=request.context.has_local_project,
            project_path=request.context.project_path,
        )

        session.messages.append({"role": "user", "content": request.message})
        session.touch()

        messages = [
            {"role": "system", "content": COPILOT_SYSTEM},
            *session.messages,
        ]

        full_reply = []
        async for token in self.llm.stream(messages):
            full_reply.append(token)
            yield f"data: {token}\n\n"

        # Save complete reply to session
        complete = "".join(full_reply)
        session.messages.append({"role": "assistant", "content": complete})
        session.touch()

        yield "data: [DONE]\n\n"
