from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.providers.inference_base import (
    ChatCompletionResult,
    InferenceBackendError,
    InferenceTarget,
)


def estimate_prompt_tokens(messages: list[dict[str, Any]]) -> int:
    total_chars = sum(len(str(item.get("content", ""))) for item in messages)
    return max(1, total_chars // 4)


def build_mock_reply(messages: list[dict[str, Any]], model: str) -> str:
    last_user = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            last_user = str(item.get("content", "")).strip()
            break
    if any(
        item.get("role") == "system"
        and "AUTO_ROUTER_CLASSIFIER_V1" in str(item.get("content", ""))
        for item in messages
    ):
        complexity_markers = (
            "architecture",
            "debug",
            "prove",
            "refactor",
            "algorithm",
            "代码",
            "架构",
            "证明",
            "推导",
            "算法",
            "调试",
            "重构",
        )
        normalized = last_user.lower()
        return (
            "complex"
            if len(last_user) > 320 or any(marker in normalized for marker in complexity_markers)
            else "simple"
        )
    snippet = last_user[:120] if last_user else "你好"
    return (
        f"[Open Compute System Mock · {model}] 已收到：{snippet}。"
        " 这是演示回复，不代表真实 GPU 推理结果。"
    )


class MockInferenceBackend:
    async def health_check(self, target: InferenceTarget) -> bool:
        return True

    async def chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
    ) -> ChatCompletionResult:
        del temperature
        if fail_once:
            raise InferenceBackendError(
                "REPLICA_UNAVAILABLE", f"replica {target.replica_label} failed"
            )
        await asyncio.sleep(settings.mock_provider_delay_seconds)
        content = build_mock_reply(messages, target.model)
        # Cap completion by max_tokens using ~4 chars/token.
        max_chars = max(16, max_tokens * 4)
        content = content[:max_chars]
        prompt_tokens = estimate_prompt_tokens(messages)
        completion_tokens = max(1, len(content) // 4)
        return ChatCompletionResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=target.model,
            replica_label=target.replica_label,
        )

    async def stream_chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
        completion_id: str,
    ) -> AsyncIterator[str]:
        result = await self.chat_completions(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            target=target,
            fail_once=fail_once,
        )
        words = result.content.split(" ")
        for index, word in enumerate(words):
            piece = word if index == 0 else f" {word}"
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "model": target.model,
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
        final = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": target.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.prompt_tokens + result.completion_tokens,
            },
            "ocs_meta": {
                "replica_label": result.replica_label,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            },
        }
        yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
