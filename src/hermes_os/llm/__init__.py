"""LLM Adapter — provider-agnostic interface for language models."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for any LLM provider."""

    provider_name: str = "base"
    default_model: str = "unknown"

    @abstractmethod
    def chat(self, messages: List[LLMMessage], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        ...

    @abstractmethod
    def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        ...

    def embed(self, text: str, model: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError(f"embed not supported by {self.provider_name}")


class MockLLMProvider(LLMProvider):
    provider_name = "mock"
    default_model = "mock-model-v1"

    def chat(self, messages: List[LLMMessage], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        model = model or self.default_model
        reply = "這是一個 Mock 回覆，用於基底架構驗證。"
        return LLMResponse(content=reply, model=model, provider=self.provider_name, usage={"prompt_tokens": len(messages), "completion_tokens": len(reply)})

    def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        model = model or self.default_model
        reply = f"[mock 完成] {prompt[:20]}..."
        return LLMResponse(content=reply, model=model, provider=self.provider_name, usage={"prompt_tokens": len(prompt), "completion_tokens": len(reply)})


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible provider (works with OpenAI, DeepSeek, or compatible endpoints)."""

    provider_name = "openai-compatible"
    default_model = "gpt-4o-mini"

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: List[LLMMessage], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            **kwargs,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return LLMResponse(
            content=f"[{self.provider_name}] 模擬呼叫 {model} 成功 (具備 API key 後可實際傳送)",
            model=model,
            provider=self.provider_name,
            usage={},
            raw={"url": f"{self.base_url}/chat/completions", "payload": {"model": model, "messages_count": len(messages)}},
        )

    def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        model = model or self.default_model
        return LLMResponse(
            content=f"[{self.provider_name}] 模擬完成 {model} | input_len={len(prompt)}",
            model=model,
            provider=self.provider_name,
            usage={"prompt_tokens": len(prompt), "completion_tokens": 32},
        )


class LLMAdapter:
    """Facade for LLM operations across providers."""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or MockLLMProvider()
        self._history: List[Dict[str, Any]] = []

    def chat(self, messages: List[LLMMessage], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        started = time.time()
        response = self.provider.chat(messages, model=model, **kwargs)
        self._history.append({
            "type": "chat",
            "model": response.model,
            "provider": response.provider,
            "latency_ms": int((time.time() - started) * 1000),
            "usage": response.usage,
        })
        return response

    def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        started = time.time()
        response = self.provider.complete(prompt, model=model, **kwargs)
        self._history.append({
            "type": "complete",
            "model": response.model,
            "provider": response.provider,
            "latency_ms": int((time.time() - started) * 1000),
            "usage": response.usage,
        })
        return response

    def set_provider(self, provider: LLMProvider) -> None:
        self.provider = provider

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self._history[-limit:]))
