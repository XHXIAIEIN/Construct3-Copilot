"""Tests for CopilotClient — async HTTP wrapper for Core API."""
import json
import pytest
import httpx

from frontends.cli.client import CopilotClient


@pytest.fixture
def client():
    return CopilotClient(base_url="http://localhost:8767")


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_success(self, client):
        """health() returns parsed JSON from GET /health."""
        mock_response = {"status": "ok", "version": "2.0.0", "modules": []}

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/health"
            return httpx.Response(200, json=mock_response)

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.health()
        assert result == mock_response
        await client.close()

    @pytest.mark.asyncio
    async def test_is_available_true(self, client):
        """is_available() returns True when health succeeds."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, json={"status": "ok"})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.is_available() is True
        await client.close()

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self, client):
        """is_available() returns False when health fails."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(500, text="Internal Server Error")

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.is_available() is False
        await client.close()


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self, client):
        """chat() POSTs correct JSON to /chat and returns response dict."""
        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/chat"
            body = json.loads(request.content)
            assert body["message"] == "hello"
            assert body["session_id"] == "s1"
            assert body["context"]["has_local_project"] is True
            return httpx.Response(200, json={
                "session_id": "s1",
                "type": "direct_answer",
                "message": "Hi there!",
                "modules_used": [],
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.chat(
            message="hello",
            session_id="s1",
            context={"has_local_project": True},
        )
        assert result["type"] == "direct_answer"
        assert result["message"] == "Hi there!"
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_without_session_id(self, client):
        """chat() works without session_id (first turn)."""
        async def mock_handler(request: httpx.Request):
            body = json.loads(request.content)
            assert body["session_id"] is None
            return httpx.Response(200, json={
                "session_id": "new-id",
                "type": "direct_answer",
                "message": "Hello!",
                "modules_used": [],
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.chat(message="hi", session_id=None)
        assert result["session_id"] == "new-id"
        await client.close()


class TestChatStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, client):
        """chat_stream() yields individual tokens from SSE stream."""
        sse_body = "data: Hello\n\ndata:  world\n\ndata: [DONE]\n\n"

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/chat/stream"
            return httpx.Response(200, text=sse_body, headers={
                "content-type": "text/event-stream",
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        tokens = []
        async for chunk in client.chat_stream(message="test"):
            tokens.append(chunk)
        assert tokens == ["Hello", " world"]
        await client.close()

    @pytest.mark.asyncio
    async def test_stream_json_fallback(self, client):
        """chat_stream() yields full JSON dict for JSON track responses."""
        response_dict = {
            "session_id": "s1", "type": "generation",
            "message": "Done", "data": {"delivery": "clipboard"},
            "modules_used": ["llm"],
        }
        sse_body = f"data: {json.dumps(response_dict)}\n\ndata: [DONE]\n\n"

        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, text=sse_body, headers={
                "content-type": "text/event-stream",
            })

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        results = []
        async for chunk in client.chat_stream(message="test"):
            results.append(chunk)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["type"] == "generation"
        await client.close()


class TestSession:
    @pytest.mark.asyncio
    async def test_get_session(self, client):
        """get_session() fetches session by ID."""
        session_data = {"session_id": "s1", "messages": [], "turn_count": 0}

        async def mock_handler(request: httpx.Request):
            assert request.url.path == "/session/s1"
            return httpx.Response(200, json=session_data)

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        result = await client.get_session("s1")
        assert result["session_id"] == "s1"
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        """delete_session() returns True on success."""
        async def mock_handler(request: httpx.Request):
            assert request.method == "DELETE"
            return httpx.Response(200, json={"deleted": True})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.delete_session("s1") is True
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, client):
        """delete_session() returns False on 404."""
        async def mock_handler(request: httpx.Request):
            return httpx.Response(404, json={"detail": "Session not found"})

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            base_url="http://localhost:8767",
        )
        assert await client.delete_session("nonexistent") is False
        await client.close()
