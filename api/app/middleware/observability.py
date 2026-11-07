import logging
import re
import time
import uuid

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
REQUEST_COUNT = Counter(
    "open_compute_system_http_requests_total", "HTTP requests", ("method", "route", "status")
)
REQUEST_DURATION = Histogram(
    "open_compute_system_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
)
logger = logging.getLogger("open_compute_system.http")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", request.url.path)
        duration = time.perf_counter() - started
        REQUEST_COUNT.labels(request.method, route, str(response.status_code)).inc()
        REQUEST_DURATION.labels(request.method, route).observe(duration)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return response


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
