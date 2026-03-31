"""
Copilot Core — FastAPI application.

Unified orchestration API serving all frontends (CLI, Skill, Web, Bridge).
"""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.config import COPILOT_PORT
from src.llm.client import LLMClient
from src.modules.rag_client import RAGClient
from src.modules.clipboard_client import ClipboardClient
from src.modules.mcp_bridge import MCPBridge
from src.modules.health import HealthChecker
from src.orchestrator.session import SessionManager
from src.orchestrator.pipeline import Pipeline
from src.orchestrator.degradation import assess_capabilities
from src.schemas.api import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)

# ── Application components ───────────────────────────────────────────────

llm = LLMClient.from_config()
rag = RAGClient()
clipboard = ClipboardClient()
mcp = MCPBridge()
sessions = SessionManager()
pipeline = Pipeline(llm=llm, sessions=sessions)
health_checker = HealthChecker(llm=llm, rag=rag, clipboard=clipboard, mcp=mcp)

# ── FastAPI app ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Construct 3 Copilot Core",
    description="Semantic understanding engine + orchestration service for Construct 3",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lifecycle ────────────────────────────────────────────────────────────

@app.on_event("shutdown")
async def shutdown():
    await rag.close()
    await clipboard.close()


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Core + module health status."""
    modules, status = await health_checker.check_all()
    caps = assess_capabilities(status)

    if not caps["operational"]:
        overall = "error"
    elif caps.get("warnings"):
        overall = "degraded"
    else:
        overall = "ok"

    return HealthResponse(status=overall, version="2.0.0", modules=modules)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main conversation endpoint — all frontends use this."""
    return await pipeline.process(request)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming conversation endpoint."""
    return StreamingResponse(
        pipeline.process_stream(request),
        media_type="text/event-stream",
    )


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session state."""
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Clear a session."""
    deleted = sessions.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# ── Entrypoint ───────────────────────────────────────────────────────────

def main():
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info(f"Starting Copilot Core on :{COPILOT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=COPILOT_PORT)


if __name__ == "__main__":
    main()
