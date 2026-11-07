from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import AgentSettings, get_settings
from app.runtime import (
    DeploymentConflictError,
    DeploymentOperationError,
    DockerUnavailableError,
    DockerVLLMRuntime,
    RuntimeErrorBase,
)
from app.schemas import DeploymentCreateRequest, DeploymentResponse, NodeInfoResponse


def create_app(
    *,
    settings: AgentSettings | None = None,
    runtime: DockerVLLMRuntime | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    active_runtime = runtime or DockerVLLMRuntime(active_settings)
    application = FastAPI(
        title="Open Compute System Node Agent",
        version="0.1.0",
        docs_url="/docs" if active_settings.agent_env != "production" else None,
        redoc_url=None,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=active_settings.allowed_hosts,
    )

    async def require_agent_token(
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = active_settings.agent_token.get_secret_value()
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AGENT_TOKEN_REQUIRED"},
            )
        supplied = authorization.removeprefix("Bearer ").strip()
        if not secrets.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AGENT_TOKEN_INVALID"},
            )

    def map_runtime_error(exc: RuntimeErrorBase) -> HTTPException:
        status_code = 409 if isinstance(exc, DeploymentConflictError) else 503
        if isinstance(exc, DeploymentOperationError):
            status_code = 422
        if isinstance(exc, DockerUnavailableError):
            status_code = 503
        return HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        )

    @application.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/v1/node", response_model=NodeInfoResponse)
    async def node_info(_: None = Depends(require_agent_token)) -> NodeInfoResponse:
        return await active_runtime.node_info()

    @application.get(
        "/v1/deployments/{deployment_id}",
        response_model=DeploymentResponse,
    )
    async def get_deployment(
        deployment_id: str = Path(
            min_length=5,
            max_length=48,
            pattern=r"^[a-z0-9][a-z0-9_-]+$",
        ),
        _: None = Depends(require_agent_token),
    ) -> DeploymentResponse:
        try:
            return await active_runtime.get_deployment(deployment_id)
        except RuntimeErrorBase as exc:
            raise map_runtime_error(exc) from exc

    @application.post(
        "/v1/deployments",
        response_model=DeploymentResponse,
        status_code=201,
    )
    async def create_deployment(
        payload: DeploymentCreateRequest,
        _: None = Depends(require_agent_token),
    ) -> DeploymentResponse:
        try:
            return await active_runtime.create_deployment(payload)
        except RuntimeErrorBase as exc:
            raise map_runtime_error(exc) from exc

    @application.delete(
        "/v1/deployments/{deployment_id}",
        response_model=DeploymentResponse,
    )
    async def delete_deployment(
        deployment_id: str = Path(
            min_length=5,
            max_length=48,
            pattern=r"^[a-z0-9][a-z0-9_-]+$",
        ),
        _: None = Depends(require_agent_token),
    ) -> DeploymentResponse:
        try:
            return await active_runtime.remove_deployment(deployment_id)
        except RuntimeErrorBase as exc:
            raise map_runtime_error(exc) from exc

    return application


app = create_app()
