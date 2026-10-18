"""Check native protocol messages without sending cloud requests."""
import json
import unittest
from unittest.mock import patch

try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import APIStatusError
from qqbot.anthropic_client import AnthropicClient


class AnthropicTests(unittest.TestCase):
    def test_official_endpoint_selects_native_client(self):
        from qqbot import model_client
        with patch.object(model_client, "BASE_URL", "https://api.anthropic.com/v1"), \
             patch.dict("os.environ", {"C3BOT_API_PROTOCOL": "auto", "C3BOT_API_KEY_ENV": "", "C3BOT_API_KEY": "key-placeholder"}):
            client = model_client.create_client()
        self.assertIsInstance(client, AnthropicClient)
        client.http.close()

    def test_tool_turn_preserves_blocks_results_and_token_counts(self):
        requests = []
        blocks = [{"type": "thinking", "thinking": "reason-placeholder", "signature": "signature-placeholder"},
                  {"type": "tool_use", "id": "call-placeholder", "name": "lookup", "input": {"word": "example"}}]
        def reply(request):
            requests.append(json.loads(request.content))
            self.assertEqual(str(request.url), "https://api.anthropic.com/v1/messages")
            self.assertEqual(request.headers["x-api-key"], "key-placeholder")
            return httpx.Response(200, json={"id": "response-placeholder", "model": "model-placeholder", "content": blocks,
                "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 3, "cache_read_input_tokens": 5}})
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com/v1", client=http)
            messages = [{"role": "system", "content": "system-placeholder"}, {"role": "user", "content": "question-placeholder"}]
            tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
            result = client.chat.completions.create(model="model-placeholder", messages=messages, tools=tools)
            message = result.choices[0].message
            self.assertEqual(message.tool_calls[0].function.name, "lookup")
            self.assertEqual(result.usage.prompt_tokens, 15)
            client.chat.completions.create(model="model-placeholder", messages=messages + [message.model_dump(exclude_none=True),
                {"role": "tool", "tool_call_id": "call-placeholder", "content": "tool-result"}])
        self.assertEqual(requests[0]["system"], "system-placeholder")
        self.assertEqual(requests[0]["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual(requests[1]["messages"][1]["content"], blocks)
        self.assertEqual(requests[1]["messages"][2]["content"][0]["type"], "tool_result")

    def test_error_message_does_not_repeat_provider_body_or_credentials(self):
        def reply(request):
            return httpx.Response(401, json={"error": "key-placeholder"})
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            with self.assertRaises(APIStatusError) as error:
                client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}])
        self.assertNotIn("key-placeholder", str(error.exception))
