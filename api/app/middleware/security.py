import hmac
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_session

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_allowed(value: str) -> bool:
    parsed = urlparse(value)
    return any(
        (parsed.scheme, parsed.netloc) == (configured.scheme, configured.netloc)
        for configured in map(urlparse, settings.allowed_origins)
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        auth = request.headers.get("authorization", "")
        if path.endswith("/chat/completions") and auth.lower().startswith("bearer "):
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if origin and not _origin_allowed(origin):
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "CSRF_ORIGIN_REJECTED", "message": "请求来源无效"}},
            )
        if not origin and referer and not _origin_allowed(referer):
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "CSRF_ORIGIN_REJECTED", "message": "请求来源无效"}},
            )

        session_token = request.cookies.get(settings.session_cookie)
        if session_token:
            payload = decode_session(session_token)
            if payload:
                cookie_token = request.cookies.get(settings.csrf_cookie, "")
                header_token = request.headers.get("X-CSRF-Token", "")
                expected = str(payload.get("csrf", ""))
                valid = bool(
                    expected
                    and cookie_token
                    and header_token
                    and hmac.compare_digest(expected, cookie_token)
                    and hmac.compare_digest(expected, header_token)
                )
                if not valid:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": {
                                "code": "CSRF_TOKEN_INVALID",
                                "message": "安全令牌无效",
                            }
                        },
                    )
        return await call_next(request)
