from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import settings
from app.models import ApiKey


@dataclass
class _Window:
    requests: int = 0
    tokens: int = 0


_windows: dict[tuple[str, int], _Window] = {}
_lock = asyncio.Lock()


def _raise_rate_limit(code: str, message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": code, "message": message},
        headers={"Retry-After": "60"},
    )


async def _consume_local(api_key: ApiKey, token_budget: int, minute: int) -> None:
    async with _lock:
        for key in [key for key in _windows if key[1] < minute - 1]:
            _windows.pop(key, None)
        window = _windows.setdefault((api_key.id, minute), _Window())
        if window.requests + 1 > api_key.rpm_limit:
            _raise_rate_limit("KEY_RPM_LIMIT", "该 API Key 已达到每分钟请求上限")
        if window.tokens + token_budget > api_key.tpm_limit:
            _raise_rate_limit("KEY_TPM_LIMIT", "该 API Key 已达到每分钟 Token 上限")
        window.requests += 1
        window.tokens += token_budget


async def _consume_redis(api_key: ApiKey, token_budget: int, minute: int) -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    base = f"ocs:inference:limit:{api_key.id}:{minute}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(f"{base}:requests")
            pipe.expire(f"{base}:requests", 120)
            pipe.incrby(f"{base}:tokens", token_budget)
            pipe.expire(f"{base}:tokens", 120)
            requests, _, tokens, _ = await pipe.execute()
    finally:
        await redis.aclose()
    if int(requests) > api_key.rpm_limit:
        _raise_rate_limit("KEY_RPM_LIMIT", "该 API Key 已达到每分钟请求上限")
    if int(tokens) > api_key.tpm_limit:
        _raise_rate_limit("KEY_TPM_LIMIT", "该 API Key 已达到每分钟 Token 上限")


async def consume_api_key_limit(api_key: ApiKey, *, token_budget: int) -> None:
    minute = int(time.time() // 60)
    if settings.app_env == "production":
        await _consume_redis(api_key, token_budget, minute)
    else:
        await _consume_local(api_key, token_budget, minute)
