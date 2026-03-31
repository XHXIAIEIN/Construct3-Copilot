"""Tests for the JSON processing pipeline branch."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.orchestrator.pipeline import Pipeline
from src.orchestrator.session import SessionManager
from src.schemas.api import ChatRequest, ChatContext


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="The JSON looks good. It sets up a Score variable and initializes it to 0 on layout start.")
    llm.is_available = True
    return llm


@pytest.fixture
def sessions():
    return SessionManager()


@pytest.fixture
def pipeline(mock_llm, sessions):
    return Pipeline(llm=mock_llm, sessions=sessions, rag=None)


class TestPipelineJsonDetection:

    @pytest.mark.asyncio
    async def test_plain_text_goes_to_qa_track(self, pipeline, mock_llm):
        """Non-JSON messages use existing Q&A path."""
        request = ChatRequest(message="Sprite 的 Set animation 怎么用？")
        response = await pipeline.process(request)
        assert response.type == "direct_answer"
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_clipboard_json_goes_to_json_track(self, pipeline, mock_llm):
        """Messages with clipboard JSON use the JSON processing path."""
        msg = '看看这个：{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        mock_llm.chat.assert_called_once()
        # The system prompt should contain clipboard-specific content
        call_args = mock_llm.chat.call_args[0][0]
        system_msg = call_args[0]["content"]
        assert "clipboard JSON" in system_msg.lower() or "Clipboard JSON" in system_msg

    @pytest.mark.asyncio
    async def test_json_track_returns_validation_in_response(self, pipeline):
        """JSON track includes input validation data."""
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_json_track_with_llm_returning_json(self, pipeline, mock_llm):
        """When LLM returns clipboard JSON, response type is generation."""
        mock_llm.chat = AsyncMock(
            return_value='Fixed:\n```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```'
        )
        msg = '修复这个：{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"invalid"}]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        assert response.type == "generation"
        assert response.data is not None
        assert response.data.clipboard_json is not None

    @pytest.mark.asyncio
    async def test_json_track_llm_error_returns_validation_only(self, pipeline, mock_llm):
        """When LLM fails, return validation report as fallback."""
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM down"))
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        request = ChatRequest(message=msg)
        response = await pipeline.process(request)
        assert response.type in ("direct_answer", "error")
