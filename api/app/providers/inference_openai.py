from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.inference_base import (
    ChatCompletionResult,
    InferenceBackendError,
    InferenceTarget,
)


def _url(target: InferenceTarget, path: str) -> str:
    return f"{target.endpoint.rstrip('/')}/{path.lstrip('/')}"


def _headers(target: InferenceTarget) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if target.api_key:
        headers["Authorization"] = f"Bearer {target.api_key}"
    return headers


def _error_for_status(status_code: int) -> InferenceBackendError:
    if status_code in {401, 403}:
        return InferenceBackendError(
            "UPSTREAM_AUTH_FAILED", "推理端点鉴权失败，请联系运营人员"
        )
    if status_code == 429:
        return InferenceBackendError("UPSTREAM_CAPACITY_LIMIT", "推理端点容量不足")
    if status_code >= 500:
        return InferenceBackendError("UPSTREAM_UNAVAILABLE", "推理端点暂不可用")
    return InferenceBackendError("UPSTREAM_REQUEST_REJECTED", "推理端点拒绝了请求")


class OpenAICompatibleInferenceBackend:
    async def health_check(self, target: InferenceTarget) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=min(target.timeout_seconds, 15),
                follow_redirects=False,
            ) as client:
                response = await client.get(_url(target, "models"), headers=_headers(target))
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
    ) -> ChatCompletionResult:
        del fail_once
        payload = {
            "model": target.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        try:
            async with httpx.AsyncClient(
                timeout=target.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    _url(target, "chat/completions"),
                    headers=_headers(target),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise InferenceBackendError("UPSTREAM_TIMEOUT", "推理端点响应超时") from exc
        except httpx.HTTPError as exc:
            raise InferenceBackendError("UPSTREAM_UNAVAILABLE", "无法连接推理端点") from exc

        if response.status_code >= 400:
            raise _error_for_status(response.status_code)
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            usage = body["usage"]
            prompt_tokens = int(usage["prompt_tokens"])
            completion_tokens = int(usage["completion_tokens"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InferenceBackendError(
                "UPSTREAM_RESPONSE_INVALID",
                "推理端点未返回可计费的 OpenAI 兼容响应",
            ) from exc
        if not isinstance(content, str):
            raise InferenceBackendError(
                "UPSTREAM_RESPONSE_INVALID", "推理端点返回的内容格式不受支持"
            )
        if prompt_tokens < 0 or completion_tokens < 0:
            raise InferenceBackendError(
                "UPSTREAM_USAGE_INVALID", "推理端点返回了无效 Token 用量"
            )
        return ChatCompletionResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=target.model,
            replica_label=target.replica_label,
        )

    def stream_chat_completions(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None,
        target: InferenceTarget,
        fail_once: bool = False,
        completion_id: str,
    ) -> AsyncIterator[str]:
        del messages, max_tokens, temperature, target, fail_once, completion_id
        raise NotImplementedError(
            "The gateway settles a non-stream upstream response before emitting SSE"
        )
