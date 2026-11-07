from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.models import InferenceNode


class AgentClientError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AgentNodeInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    docker_available: bool
    docker_version: str | None
    gpus: list[dict[str, Any]]
    agent_version: str


class AgentDeployment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    deployment_id: str
    container_name: str
    model_id: str
    served_model_name: str
    image: str
    gpu_device_ids: list[int]
    host_port: int
    endpoint: str
    status: str
    exit_code: int | None = None


def validate_agent_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AgentClientError(
            "INVALID_AGENT_URL",
            "Agent URL 必须是无内嵌凭据、查询参数或片段的 HTTP(S) base URL",
        )
    return normalized


class NodeAgentClient:
    def __init__(self, node: InferenceNode) -> None:
        self.node = node
        self.base_url = validate_agent_url(node.agent_url)
        self.token = os.environ.get(node.agent_token_env_var)
        if not self.token:
            raise AgentClientError("AGENT_TOKEN_MISSING", "节点 Agent Token 未配置")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: int = 150,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=json_body,
                )
        except httpx.TimeoutException as exc:
            raise AgentClientError("AGENT_TIMEOUT", "节点 Agent 响应超时") from exc
        except httpx.HTTPError as exc:
            raise AgentClientError("AGENT_UNAVAILABLE", "无法连接节点 Agent") from exc
        if response.status_code >= 400:
            code = "AGENT_REQUEST_FAILED"
            try:
                code = str(response.json().get("detail", {}).get("code") or code)
            except (ValueError, AttributeError):
                pass
            raise AgentClientError(code, "节点 Agent 拒绝了请求")
        try:
            return response.json()
        except ValueError as exc:
            raise AgentClientError("AGENT_RESPONSE_INVALID", "节点 Agent 返回无效响应") from exc

    async def node_info(self) -> AgentNodeInfo:
        try:
            return AgentNodeInfo.model_validate(await self._request("GET", "/v1/node"))
        except ValidationError as exc:
            raise AgentClientError("AGENT_RESPONSE_INVALID", "节点信息格式无效") from exc

    async def create_deployment(self, payload: dict[str, Any]) -> AgentDeployment:
        try:
            return AgentDeployment.model_validate(
                await self._request(
                    "POST",
                    "/v1/deployments",
                    json_body=payload,
                    timeout_seconds=180,
                )
            )
        except ValidationError as exc:
            raise AgentClientError("AGENT_RESPONSE_INVALID", "部署响应格式无效") from exc

    async def get_deployment(self, deployment_id: str) -> AgentDeployment:
        try:
            return AgentDeployment.model_validate(
                await self._request("GET", f"/v1/deployments/{deployment_id}")
            )
        except ValidationError as exc:
            raise AgentClientError("AGENT_RESPONSE_INVALID", "部署状态格式无效") from exc

    async def remove_deployment(self, deployment_id: str) -> AgentDeployment:
        try:
            return AgentDeployment.model_validate(
                await self._request("DELETE", f"/v1/deployments/{deployment_id}")
            )
        except ValidationError as exc:
            raise AgentClientError("AGENT_RESPONSE_INVALID", "部署删除响应格式无效") from exc
