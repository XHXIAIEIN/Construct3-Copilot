"""Session management — in-memory multi-turn conversation state."""
import time
import uuid
import logging
from typing import Optional

from src.config import SESSION_TTL_SECONDS
from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    """In-memory session store with TTL-based expiry."""

    def __init__(self, ttl: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, SessionState] = {}
        self._ttl = ttl

    def create(
        self,
        has_local_project: bool = False,
        project_path: Optional[str] = None,
    ) -> SessionState:
        session_id = uuid.uuid4().hex[:12]
        session = SessionState(
            session_id=session_id,
            has_local_project=has_local_project,
            project_path=project_path,
        )
        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.updated_at > self._ttl:
            self.delete(session_id)
            logger.info(f"Session expired: {session_id}")
            return None
        return session

    def get_or_create(
        self,
        session_id: Optional[str],
        has_local_project: bool = False,
        project_path: Optional[str] = None,
    ) -> SessionState:
        if session_id:
            session = self.get(session_id)
            if session:
                return session
        return self.create(has_local_project, project_path)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def cleanup_expired(self):
        """Remove all expired sessions."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.updated_at > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    @property
    def active_count(self) -> int:
        return len(self._sessions)
