"""The model connection read from the settings dict: which server, which model, how long to wait, which switch
turns thinking off, and which protocol the server speaks."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def protocol_of(profile: dict) -> str:
    """"auto" means Anthropic's protocol for Anthropic's own server and OpenAI-compatible for every other one."""
    protocol = profile.get("protocol") or "auto"
    if protocol == "auto":
        return "anthropic" if urlsplit(profile.get("base_url", "")).hostname == "api.anthropic.com" else "openai"
    return protocol


@dataclass(frozen=True)
class ModelSettings:
    base_url: str
    model: str
    protocol: str
    timeout: int
    request_options: dict = field(default_factory=dict)
    # the tool loop of an answer that makes or changes a project: thinking on, with room and time for it
    project_options: dict = field(default_factory=dict)
    project_timeout: int = 120
    local: bool = False
    zhipu: bool = False
    siliconflow: bool = False
    yield_logs: tuple[str, ...] = ()


def from_settings(settings: dict) -> ModelSettings:
    # C3BOT_BASE_URL points at any OpenAI-compatible server, e.g. Ollama's http://localhost:11434/v1
    base_url = settings.get("C3BOT_BASE_URL") or "https://api.deepseek.com"
    siliconflow = "siliconflow" in base_url  # hosted Chinese models, for comparison runs (2026-10-09)
    zhipu = "bigmodel.cn" in base_url  # glm-4.7-flash, free (2026-10-09)
    local = urlsplit(base_url).hostname in {"localhost", "127.0.0.1", "::1"}
    # thinking off: DeepSeek reads "thinking", Ollama reads reasoning_effort "none", SiliconFlow reads enable_thinking;
    # C3BOT_EXTRA_BODY (JSON) replaces it for a model that wants another switch
    no_think = ({"reasoning_effort": settings.get("C3BOT_REASONING") or "none", "max_tokens": 6000} if local
                else {"enable_thinking": False, "max_tokens": 6000} if siliconflow
                else {"thinking": {"type": "disabled"}, "max_tokens": 6000} if zhipu
                else {"thinking": {"type": "disabled"}} if "api.deepseek.com" in base_url else {})
    protocol = protocol_of({"protocol": settings.get("C3BOT_API_PROTOCOL"), "base_url": base_url})
    # thinking on, for making or changing a project; Claude Opus 5.5 always thinks, so there only its effort goes up
    # (default medium). A model none of these names gets nothing, as before
    effort = settings.get("C3BOT_REASONING")
    think = ({"reasoning_effort": effort if effort and effort != "none" else "medium", "max_tokens": 16000} if local
             else {"enable_thinking": True, "max_tokens": 16000} if siliconflow
             else {"thinking": {"type": "enabled"}, "max_tokens": 16000} if zhipu
             else {"thinking": {"type": "enabled"}, "max_tokens": 16000} if "api.deepseek.com" in base_url
             else {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}, "max_tokens": 16000}
             if protocol == "anthropic" else {})
    if settings.get("C3BOT_EXTRA_BODY"):
        no_think = json.loads(settings["C3BOT_EXTRA_BODY"])
        think = no_think  # a switch set by hand holds for every answer unless the project one is set too
    if settings.get("C3BOT_EXTRA_BODY_PROJECT"):
        think = json.loads(settings["C3BOT_EXTRA_BODY_PROJECT"])
    # C3BOT_THINKING: auto (default) thinks for projects only, off never asks for it, on asks for it in every call
    mode = (settings.get("C3BOT_THINKING") or "auto").strip().lower()
    if mode == "off":
        think = no_think
    elif mode == "on":
        no_think = think
    timeout = 600 if local else 300 if siliconflow or zhipu else 120  # a local model reads a long prompt slowly
    return ModelSettings(
        base_url=base_url,
        model=settings.get("C3BOT_MODEL") or settings.get("DEEPSEEK_MODEL") or "deepseek-flash",
        protocol=protocol, timeout=timeout,
        request_options=no_think, project_options=think,
        project_timeout=timeout if think == no_think else max(timeout, 600),
        local=local, zhipu=zhipu, siliconflow=siliconflow,
        # logs of a TTS server sharing the GPU, separated by ";"; empty: never wait
        yield_logs=tuple(p for p in (settings.get("C3BOT_YIELD_LOGS") or "").split(";") if p),
    )


def api_key(model: ModelSettings, settings: dict) -> str | None:
    reference = settings.get("C3BOT_API_KEY_ENV")
    key = settings.get(reference) if reference else settings.get("C3BOT_API_KEY") or settings.get("QQBOT_API_KEY")
    if not key:
        key = (settings.get("ZHIPU_API_KEY") if model.zhipu else
               settings.get("SILICONFLOW_API_KEY") if model.siliconflow else
               "ollama" if model.local else settings.get("DEEPSEEK_API_KEY"))
    return key
