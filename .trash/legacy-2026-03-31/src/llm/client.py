"""
LLM Client — unified interface for language model inference.

Supports three providers:
- ollama:      Local Ollama service
- openai:      OpenAI-compatible API (Kimi, DeepSeek, OpenAI, etc.)
- huggingface: Local HuggingFace transformers model
"""
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class LLMClient:

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        provider: str = "ollama",
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self._client = None
        self._hf_model = None
        self._hf_tokenizer = None
        self._available = None

    # ── API-based clients ─────────────────────────────────────────────────

    @property
    def client(self):
        """Lazy-load API client. Returns None for huggingface provider."""
        if self.provider == "huggingface":
            return None
        if self._client is None:
            if self.provider == "ollama":
                try:
                    import ollama
                    self._client = ollama.Client(host=self.base_url)
                except ImportError:
                    logger.warning("ollama not installed")
            else:
                try:
                    from openai import OpenAI
                    self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
                except ImportError:
                    logger.warning("openai not installed")
        return self._client

    def _chat_ollama(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    def _chat_openai(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model, messages=messages,
        )
        return response.choices[0].message.content

    # ── HuggingFace local inference ───────────────────────────────────────

    def _load_hf(self):
        """Lazy-load HuggingFace model and tokenizer."""
        if self._hf_model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"[HF] Loading model: {self.model} ...")
        self._hf_tokenizer = AutoTokenizer.from_pretrained(self.model)

        model_cls = self._resolve_model_class(AutoModelForCausalLM)
        load_kwargs = dict(low_cpu_mem_usage=True)
        if torch.cuda.is_available():
            logger.info("[HF] GPU detected, loading to CUDA ...")
            load_kwargs["dtype"] = torch.bfloat16
            self._hf_model = model_cls.from_pretrained(self.model, **load_kwargs)
            self._strip_vision_modules(self._hf_model)
            self._hf_model = self._hf_model.to("cuda")
            torch.cuda.empty_cache()
        else:
            load_kwargs["dtype"] = "auto"
            self._hf_model = model_cls.from_pretrained(self.model, **load_kwargs)

        device = next(self._hf_model.parameters()).device
        logger.info(f"[HF] Model loaded, device: {device}")

    def _strip_vision_modules(self, model):
        """Remove vision encoder and multimodal modules to save VRAM."""
        import gc
        removed = []
        for attr in ("visual", "mtp"):
            if hasattr(model, attr):
                delattr(model, attr)
                removed.append(attr)
            elif hasattr(model, "model") and hasattr(model.model, attr):
                delattr(model.model, attr)
                removed.append(f"model.{attr}")
        if removed:
            gc.collect()
            logger.info(f"[HF] Stripped vision modules: {removed}")

    def _resolve_model_class(self, default_cls):
        """Pick the right model class based on config.json architectures."""
        from pathlib import Path

        config_path = Path(self.model) / "config.json"
        if not config_path.exists():
            return default_cls

        with open(config_path) as f:
            arch_list = json.load(f).get("architectures", [])

        if not arch_list:
            return default_cls

        arch_name = arch_list[0]
        if arch_name.endswith("ForConditionalGeneration"):
            import transformers
            cls = getattr(transformers, arch_name, None)
            if cls is not None:
                logger.info(f"[HF] Using {arch_name} (VLM architecture)")
                return cls

        return default_cls

    @property
    def _is_qwen3(self) -> bool:
        return "qwen3" in self.model.lower()

    def _apply_chat_template(self, messages: List[Dict[str, str]]) -> str:
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        if self._is_qwen3:
            kwargs["enable_thinking"] = False
        return self._hf_tokenizer.apply_chat_template(messages, **kwargs)

    def _generate_kwargs(self) -> dict:
        if self._is_qwen3:
            return {"temperature": 0.7, "top_p": 0.8, "top_k": 20}
        return {"temperature": 0.7, "top_p": 0.9}

    def _chat_hf(self, messages: List[Dict[str, str]]) -> str:
        import torch
        self._load_hf()
        tok = self._hf_tokenizer
        text = self._apply_chat_template(messages)
        inputs = tok([text], return_tensors="pt").to(self._hf_model.device)
        with torch.no_grad():
            output = self._hf_model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=True,
                pad_token_id=tok.eos_token_id,
                **self._generate_kwargs(),
            )
        generated = output[0][inputs.input_ids.shape[-1]:]
        return tok.decode(generated, skip_special_tokens=True)

    def _stream_hf(self, messages: List[Dict[str, str]]):
        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread

        self._load_hf()
        tok = self._hf_tokenizer
        text = self._apply_chat_template(messages)
        inputs = tok([text], return_tensors="pt").to(self._hf_model.device)
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)

        def _run():
            with torch.no_grad():
                self._hf_model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=True,
                    pad_token_id=tok.eos_token_id,
                    streamer=streamer,
                    **self._generate_kwargs(),
                )

        Thread(target=_run, daemon=True).start()
        yield from streamer

    # ── Health check ──────────────────────────────────────────────────────

    def check_health(self) -> tuple[bool, str]:
        if self.provider == "huggingface":
            try:
                from transformers import AutoConfig
                AutoConfig.from_pretrained(self.model, local_files_only=True)
                self._available = True
                return True, f"HuggingFace model cached: {self.model}"
            except Exception as e:
                self._available = False
                return False, f"Model not cached locally: {e}"

        if self.client is None:
            self._available = False
            return False, f"{self.provider} package not installed"
        try:
            if self.provider == "ollama":
                self.client.list()
            else:
                self.client.models.list()
            self._available = True
            return True, "LLM service is healthy"
        except Exception as e:
            self._available = False
            return False, f"LLM connection failed: {e}"

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self.check_health()
        return self._available or False

    # ── Public generation methods ─────────────────────────────────────────

    def generate(self, prompt: str, system: str = "") -> str:
        """Single-turn generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            return self.chat(messages)
        except Exception as e:
            return f"LLM error: {e}"

    def generate_stream(self, prompt: str, system: str = ""):
        """Single-turn streaming generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            if self.provider == "huggingface":
                yield from self._stream_hf(messages)
            elif self.provider == "ollama":
                stream = self.client.chat(model=self.model, messages=messages, stream=True)
                for chunk in stream:
                    if "message" in chunk and "content" in chunk["message"]:
                        yield chunk["message"]["content"]
            else:
                stream = self.client.chat.completions.create(
                    model=self.model, messages=messages, stream=True,
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except Exception as e:
            yield f"LLM error: {e}"

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Multi-turn chat."""
        try:
            if self.provider == "huggingface":
                return self._chat_hf(messages)
            elif self.provider == "ollama":
                return self._chat_ollama(messages)
            else:
                return self._chat_openai(messages)
        except Exception as e:
            return f"LLM error: {e}"
