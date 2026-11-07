import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


def rate_limit(name: str, *, requests: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        if settings.app_env == "test":
            return
        client = request.client.host if request.client else "unknown"
        key = f"{name}:{client}"
        now = time.monotonic()
        async with _lock:
            bucket = _buckets[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"},
                    headers={"Retry-After": str(window_seconds)},
                )
            bucket.append(now)

    return dependency
