from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ChatCompletionResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    replica_label: str


@dataclass(slots=True)
class InferenceTarget:
    endpoint: str
    model: str
    replica_label: str
    api_key: str | None
    timeout_seconds: int


class InferenceBackendError(RuntimeError):
    def __init__(self, code: str, message: str = "Inference backend failed") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class InferenceBackend(Protocol):
    async def health_check(self, target: InferenceTarget) -> bool: ...

    async def chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
    ) -> ChatCompletionResult: ...

    def stream_chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
        completion_id: str,
    ) -> AsyncIterator[str]: ...
