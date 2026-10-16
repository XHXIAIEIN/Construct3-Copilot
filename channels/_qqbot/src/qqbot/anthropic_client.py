"""Adapt text and client-tool turns to Anthropic's Messages protocol."""
import json
import time
from types import SimpleNamespace

try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import APIStatusError, BadRequestError
from openai.types.chat import ChatCompletion


class AnthropicClient:
    def __init__(self, *, api_key, base_url, client=None):
        self.key = api_key
        self.url = base_url.rstrip("/")
        if not self.url.endswith("/v1"):
            self.url += "/v1"
        self.url += "/messages"
        self.http = client or httpx.Client(follow_redirects=False)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, *, model, messages, tools=None, tool_choice=None, timeout=120,
               max_tokens=6000, extra_body=None, response_format=None, **options):
        system, turns = [], []
        for message in messages:
            role = message["role"]
            content = message.get("content") or ""
            if role == "system":
                system.append(content)
                continue
            if role == "tool":
                role = "user"
                blocks = [{"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": content}]
            elif role == "assistant" and message.get("anthropic_content"):
                blocks = message["anthropic_content"]
            else:
                if not isinstance(content, str):
                    raise ValueError("原生 Anthropic 适配器支持文本与工具消息。")
                blocks = [{"type": "text", "text": content}] if content else []
                for call in message.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"],
                                   "input": json.loads(call["function"]["arguments"])})
            if blocks:
                if turns and turns[-1]["role"] == role:
                    turns[-1]["content"].extend(blocks)
                else:
                    turns.append({"role": role, "content": list(blocks)})
        if response_format:
            system.append("Return one JSON object, without surrounding text.")
        payload = {"model": model, "max_tokens": max_tokens, "messages": turns}
        if system:
            payload["system"] = "\n\n".join(system)
        if tools:
            payload["tools"] = [{"name": t["function"]["name"],
                                 "description": t["function"].get("description", ""),
                                 "input_schema": t["function"]["parameters"]} for t in tools]
        if tool_choice in ("auto", "required"):
            payload["tool_choice"] = {"type": "auto" if tool_choice == "auto" else "any"}
        elif tool_choice == "none":
            payload.pop("tools", None)
        elif isinstance(tool_choice, dict):
            payload["tool_choice"] = {"type": "tool", "name": tool_choice["function"]["name"]}
        payload.update(extra_body or {})
        response = self.http.post(self.url, json=payload, timeout=timeout,
                                  headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        if response.status_code >= 300:
            error = BadRequestError if response.status_code == 400 else APIStatusError
            raise error(f"Anthropic 接口返回 HTTP {response.status_code}", response=response, body=None)
        data = response.json()
        blocks = data["content"]
        calls = [{"id": b["id"], "type": "function", "function": {
            "name": b["name"], "arguments": json.dumps(b["input"], ensure_ascii=False)}}
            for b in blocks if b["type"] == "tool_use"]
        usage = data.get("usage", {})
        return ChatCompletion.model_validate({
            "id": data["id"], "object": "chat.completion", "created": int(time.time()), "model": data.get("model", model),
            "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "length" if data.get("stop_reason") == "max_tokens" else "stop",
                         "message": {"role": "assistant", "content": "".join(b["text"] for b in blocks if b["type"] == "text"),
                                     "tool_calls": calls or None, "anthropic_content": blocks}}],
            "usage": {"prompt_tokens": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
                      "completion_tokens": usage.get("output_tokens", 0),
                      "total_tokens": sum(usage.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
                      "prompt_cache_hit_tokens": usage.get("cache_read_input_tokens", 0)},
        })
