"""Model-agnostic LLM client.

Speaks the OpenAI-compatible chat-completions wire format, which most
providers (OpenAI, OpenRouter, Together, Groq, vLLM, llama.cpp server,
LM Studio, ollama with the OpenAI shim) implement. Configure via env:

- ``PRC_MODEL``    — model identifier passed through to the provider.
- ``PRC_API_KEY``  — bearer token; optional for local servers.
- ``PRC_API_BASE`` — base URL, default ``https://api.openai.com/v1``.

A :class:`MockLLMClient` is provided for tests so the suite never makes
a real network call.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    """A single completion, normalised across providers."""

    model_config = ConfigDict(frozen=True)

    content: str
    model: str
    tokens_in: int
    tokens_out: int


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...


class MockLLMExhausted(RuntimeError):  # noqa: N818 - reads better without the suffix
    """Raised when the mock client is called past its queued responses."""


class MockLLMClient:
    """Deterministic playback client for tests.

    Queue responses in FIFO order; every call is recorded for assertion.
    """

    def __init__(self, responses: Sequence[LLMResponse] | None = None) -> None:
        self._queue: deque[LLMResponse] = deque(responses or ())
        self._calls: list[tuple[str, list[dict[str, str]]]] = []

    def queue(self, content: str, *, model: str = "mock") -> None:
        self._queue.append(
            LLMResponse(content=content, model=model, tokens_in=0, tokens_out=0)
        )

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self._calls.append((system, [dict(m) for m in messages]))
        if not self._queue:
            raise MockLLMExhausted(f"no queued responses (call #{len(self._calls)})")
        return self._queue.popleft()

    @property
    def calls(self) -> Sequence[tuple[str, list[dict[str, str]]]]:
        return tuple(self._calls)


class OpenAICompatClient:
    """Real client for any OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("PRC_API_KEY", "")
        self._api_base = (api_base or os.environ.get("PRC_API_BASE")
                          or "https://api.openai.com/v1").rstrip("/")
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        resp = await self._http.post(
            f"{self._api_base}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=self._model,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


def client_from_env() -> LLMClient:
    """Build an :class:`OpenAICompatClient` from ``PRC_*`` env vars."""
    model = os.environ.get("PRC_MODEL")
    if not model:
        raise RuntimeError("PRC_MODEL is not set")
    return OpenAICompatClient(
        model=model,
        api_key=os.environ.get("PRC_API_KEY"),
        api_base=os.environ.get("PRC_API_BASE"),
    )
