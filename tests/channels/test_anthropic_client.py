"""Check native protocol messages without sending cloud requests."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import APIStatusError
from channels.model.anthropic_client import AnthropicClient


class AnthropicTests(unittest.TestCase):
    def test_official_endpoint_selects_native_client(self):
        from channels.model.client import create_client
        from channels.model.settings import from_settings
        from channels.model.usage import Usage
        settings = {"C3BOT_BASE_URL": "https://api.anthropic.com/v1", "C3BOT_API_PROTOCOL": "auto",
                    "C3BOT_API_KEY_ENV": "", "C3BOT_API_KEY": "key-placeholder"}
        client = create_client(from_settings(settings), settings, Usage(Path("unused")))
        self.assertIsInstance(client, AnthropicClient)
        client.http.close()

    def test_settings_are_read_from_the_dict_not_the_environment(self):
        from channels.model.settings import from_settings
        with patch.dict("os.environ", {"C3BOT_BASE_URL": "https://api.anthropic.com/v1", "C3BOT_MODEL": "stale"}):
            model = from_settings({"C3BOT_BASE_URL": "http://127.0.0.1:11434/v1", "C3BOT_MODEL": "local-model"})
        self.assertEqual((model.model, model.protocol, model.local, model.timeout), ("local-model", "openai", True, 600))

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

    def test_tool_loop_calls_are_cached_and_reads_and_writes_counted_apart(self):
        from channels.model.usage import cache_counts
        requests = []
        def reply(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "response-placeholder", "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 3,
                                                     "cache_read_input_tokens": 50, "cache_creation_input_tokens": 20}})
        messages = [{"role": "system", "content": "system-placeholder"}, {"role": "user", "content": "question-placeholder"}]
        tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com/v1", client=http)
            result = client.create(model="model-placeholder", messages=messages, tools=tools)
            client.create(model="model-placeholder", messages=messages)  # a side call: sent once, never read back
            client.create(model="model-placeholder", messages=messages, tools=tools, tool_choice="none")
        self.assertEqual(requests[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(["cache_control" in r for r in requests[1:]], [False, False])
        self.assertEqual(requests[0]["system"], "system-placeholder")  # the prompt itself is unchanged
        self.assertEqual((result.usage.prompt_tokens, result.usage.total_tokens), (80, 83))  # as without caching
        self.assertEqual(cache_counts(result.usage), (50, 20))

    def test_other_servers_on_this_protocol_are_sent_no_cache_control(self):
        from channels.model.usage import cache_counts
        requests = []
        def reply(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "response-placeholder", "content": [{"type": "text", "text": "ok"}],
                                             "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 3}})
        tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://open.bigmodel.cn/api/anthropic", client=http)
            result = client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}], tools=tools)
        self.assertNotIn("cache_control", requests[0])
        self.assertEqual(result.usage.prompt_tokens, 10)
        self.assertEqual(cache_counts(result.usage), (None, None))  # not reported: unknown, not zero

    def test_image_part_becomes_a_base64_image_block(self):
        requests = []
        def reply(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "response-placeholder", "content": [{"type": "text", "text": "ok"}],
                                             "stop_reason": "end_turn", "usage": {}})
        content = [{"type": "text", "text": "question-placeholder"},
                   {"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U="}}]
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            client.create(model="model-placeholder", messages=[{"role": "user", "content": content}])
            with self.assertRaises(ValueError):  # only images already downloaded go out
                client.create(model="model-placeholder", messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}}]}])
        self.assertEqual(requests[0]["messages"][0]["content"], [
            {"type": "text", "text": "question-placeholder"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aW1hZ2U="}}])

    def test_overload_and_rate_limit_are_sent_again(self):
        statuses = [529, 429, 200]
        def reply(request):
            status = statuses.pop(0)
            if status != 200:
                return httpx.Response(status, headers={"retry-after": "2"} if status == 429 else {})
            return httpx.Response(200, json={"id": "response-placeholder", "content": [{"type": "text", "text": "ok"}],
                                             "stop_reason": "end_turn", "usage": {}})
        with httpx.Client(transport=httpx.MockTransport(reply)) as http, \
                patch("channels.model.anthropic_client.time.sleep") as sleep:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            result = client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}])
        self.assertEqual(result.choices[0].message.content, "ok")
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.5, 2.0])

    def test_lost_connection_is_sent_again_and_the_last_failure_raised(self):
        calls = []
        def reply(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(503)
        with httpx.Client(transport=httpx.MockTransport(reply)) as http, \
                patch("channels.model.anthropic_client.time.sleep"):
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            with self.assertRaises(APIStatusError):
                client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}])
        self.assertEqual(len(calls), 3)

    def test_a_refused_request_is_not_sent_again(self):
        calls = []
        def reply(request):
            calls.append(request)
            return httpx.Response(400, json={"error": "bad request"})
        with httpx.Client(transport=httpx.MockTransport(reply)) as http, \
                patch("channels.model.anthropic_client.time.sleep") as sleep:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            with self.assertRaises(APIStatusError):
                client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}])
        self.assertEqual((len(calls), sleep.call_count), (1, 0))

    def test_error_message_does_not_repeat_provider_body_or_credentials(self):
        def reply(request):
            return httpx.Response(401, json={"error": "key-placeholder"})
        with httpx.Client(transport=httpx.MockTransport(reply)) as http:
            client = AnthropicClient(api_key="key-placeholder", base_url="https://api.anthropic.com", client=http)
            with self.assertRaises(APIStatusError) as error:
                client.create(model="model-placeholder", messages=[{"role": "user", "content": "hello"}])
        self.assertNotIn("key-placeholder", str(error.exception))
