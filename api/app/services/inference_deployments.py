from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdminUser,
    InferenceDeployment,
    InferenceModel,
    InferenceNode,
    InferenceReplica,
)
from app.schemas import InferenceDeploymentCreateRequest, InferenceNodeCreateRequest
from app.services.audit import add_audit
from app.services.gateway import backend_for_model, target_for_replica
from app.services.node_agent_client import AgentClientError, NodeAgentClient, validate_agent_url

ACTIVE_DEPLOYMENT_STATES = {"pending", "provisioning", "running", "degraded"}


def _request_hash(payload: InferenceDeploymentCreateRequest) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _deployment_http_error(exc: AgentClientError) -> HTTPException:
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if exc.code in {"DEPLOYMENT_CONFLICT", "INVALID_AGENT_URL"}:
        status_code = status.HTTP_409_CONFLICT
    if exc.code in {"DEPLOYMENT_OPERATION_FAILED", "AGENT_REQUEST_FAILED"}:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )


async def create_node(
    db: AsyncSession,
    *,
    payload: InferenceNodeCreateRequest,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceNode:
    try:
        agent_url = validate_agent_url(payload.agent_url)
    except AgentClientError as exc:
        raise _deployment_http_error(exc) from exc
    existing = await db.scalar(
        select(InferenceNode.id).where(InferenceNode.agent_url == agent_url)
    )
    if existing:
        raise HTTPException(status_code=409, detail={"code": "INFERENCE_NODE_EXISTS"})
    node = InferenceNode(
        name=payload.name,
        agent_url=agent_url,
        agent_token_env_var=payload.agent_token_env_var,
        runtime_credential_env_var=payload.runtime_credential_env_var,
    )
    db.add(node)
    await db.flush()
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_node.created",
        object_type="inference_node",
        object_id=node.id,
        summary={
            "name": node.name,
            "agent_url": node.agent_url,
            "agent_token_env_var": node.agent_token_env_var,
        },
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(node)
    return node


async def check_node_health(
    db: AsyncSession,
    *,
    node_id: str,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceNode:
    node = await db.get(InferenceNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_NODE_NOT_FOUND"})
    try:
        info = await NodeAgentClient(node).node_info()
        node.status = "healthy" if info.docker_available and info.gpus else "degraded"
        node.docker_version = info.docker_version
        node.gpu_summary = info.gpus
    except AgentClientError as exc:
        node.status = "unhealthy"
        node.docker_version = None
        node.gpu_summary = []
        node.last_health_checked_at = datetime.now(UTC)
        node.version += 1
        await db.commit()
        raise _deployment_http_error(exc) from exc
    node.last_health_checked_at = datetime.now(UTC)
    node.version += 1
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_node.health_checked",
        object_type="inference_node",
        object_id=node.id,
        summary={"status": node.status, "gpu_count": len(node.gpu_summary)},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(node)
    return node


async def create_deployment(
    db: AsyncSession,
    *,
    payload: InferenceDeploymentCreateRequest,
    idempotency_key: str,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceDeployment:
    request_hash = _request_hash(payload)
    existing = await db.scalar(
        select(InferenceDeployment).where(
            InferenceDeployment.created_by == admin.id,
            InferenceDeployment.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"})
        if existing.replica_id or existing.status not in {"pending", "provisioning"}:
            return existing

    node = await db.get(InferenceNode, payload.node_id, with_for_update=True)
    model = await db.get(InferenceModel, payload.model_id)
    if not node or not node.enabled:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_NODE_NOT_FOUND"})
    if node.status != "healthy":
        raise HTTPException(
            status_code=409,
            detail={"code": "INFERENCE_NODE_UNHEALTHY", "message": "节点未通过健康检查"},
        )
    if not model or model.backend_type != "openai_compatible":
        raise HTTPException(
            status_code=422,
            detail={"code": "MODEL_BACKEND_INCOMPATIBLE"},
        )
    if not node.runtime_credential_env_var:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VLLM_CREDENTIAL_REQUIRED",
                "message": "节点必须配置 vLLM 内部 API Key 环境变量",
            },
        )
    if not os.environ.get(node.runtime_credential_env_var):
        raise HTTPException(
            status_code=503,
            detail={"code": "VLLM_CREDENTIAL_MISSING"},
        )
    known_gpu_ids = {
        int(item["index"])
        for item in node.gpu_summary
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }
    requested_gpu_ids = set(payload.gpu_device_ids)
    if not requested_gpu_ids.issubset(known_gpu_ids):
        raise HTTPException(
            status_code=422,
            detail={"code": "GPU_DEVICE_NOT_FOUND"},
        )
    active = list(
        (
            await db.scalars(
                select(InferenceDeployment).where(
                    InferenceDeployment.node_id == node.id,
                    InferenceDeployment.status.in_(ACTIVE_DEPLOYMENT_STATES),
                )
            )
        ).all()
    )
    for row in active:
        if existing and row.id == existing.id:
            continue
        if requested_gpu_ids.intersection(row.gpu_device_ids):
            raise HTTPException(status_code=409, detail={"code": "GPU_DEVICE_IN_USE"})
        if row.host_port == payload.host_port:
            raise HTTPException(status_code=409, detail={"code": "HOST_PORT_IN_USE"})

    if existing:
        deployment = existing
        # Close the read transaction before the remote call. A later row lock then observes any
        # replica attached by a concurrent recovery request.
        await db.commit()
    else:
        deployment = InferenceDeployment(
            created_by=admin.id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            model_id=model.id,
            node_id=node.id,
            model_source_id=payload.model_source_id,
            served_model_name=payload.served_model_name,
            image=payload.image,
            gpu_device_ids=payload.gpu_device_ids,
            tensor_parallel_size=payload.tensor_parallel_size,
            host_port=payload.host_port,
            max_model_len=payload.max_model_len,
            gpu_memory_utilization_milli=round(payload.gpu_memory_utilization * 1000),
            huggingface_token_env_var=payload.huggingface_token_env_var,
            status="provisioning",
        )
        db.add(deployment)
        await db.flush()
        add_audit(
            db,
            actor_type="admin",
            actor_id=admin.id,
            action="inference_deployment.requested",
            object_type="inference_deployment",
            object_id=deployment.id,
            summary={
                "model_id": model.id,
                "node_id": node.id,
                "gpu_device_ids": payload.gpu_device_ids,
                "host_port": payload.host_port,
            },
            request_id=request_id,
        )
        await db.commit()

    try:
        agent_result = await NodeAgentClient(node).create_deployment(
            {
                "deployment_id": deployment.id,
                "model_id": payload.model_source_id,
                "served_model_name": payload.served_model_name,
                "image": payload.image,
                "gpu_device_ids": payload.gpu_device_ids,
                "tensor_parallel_size": payload.tensor_parallel_size,
                "host_port": payload.host_port,
                "max_model_len": payload.max_model_len,
                "gpu_memory_utilization": payload.gpu_memory_utilization,
                "huggingface_token_env_var": payload.huggingface_token_env_var,
                "vllm_api_key_env_var": node.runtime_credential_env_var,
            }
        )
        locked_deployment = await db.scalar(
            select(InferenceDeployment)
            .where(InferenceDeployment.id == deployment.id)
            .with_for_update()
        )
        if not locked_deployment:
            raise HTTPException(status_code=404, detail={"code": "INFERENCE_DEPLOYMENT_NOT_FOUND"})
        deployment = locked_deployment
        if deployment.replica_id:
            await db.commit()
            await db.refresh(deployment)
            return deployment
        deployment.endpoint = agent_result.endpoint
        deployment.status = "provisioning"
        replica = InferenceReplica(
            model_id=model.id,
            label=f"agent-{deployment.id[-8:]}",
            endpoint=agent_result.endpoint,
            upstream_model=payload.served_model_name,
            credential_env_var=node.runtime_credential_env_var,
            timeout_seconds=120,
            weight=100,
            health_status="unknown",
            enabled=True,
        )
        db.add(replica)
        await db.flush()
        deployment.replica_id = replica.id
        deployment.deployed_at = datetime.now(UTC)
        deployment.version += 1
        await db.commit()
        await db.refresh(deployment)
        return deployment
    except AgentClientError as exc:
        locked_deployment = await db.scalar(
            select(InferenceDeployment)
            .where(InferenceDeployment.id == deployment.id)
            .with_for_update()
        )
        if not locked_deployment:
            raise HTTPException(
                status_code=404, detail={"code": "INFERENCE_DEPLOYMENT_NOT_FOUND"}
            ) from exc
        deployment = locked_deployment
        if deployment.replica_id:
            await db.commit()
            await db.refresh(deployment)
            return deployment
        deployment.status = "failed"
        deployment.error_code = exc.code
        deployment.error_summary = exc.message
        deployment.version += 1
        await db.commit()
        raise _deployment_http_error(exc) from exc


async def sync_deployment(
    db: AsyncSession,
    *,
    deployment_id: str,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceDeployment:
    deployment = await db.scalar(
        select(InferenceDeployment)
        .where(InferenceDeployment.id == deployment_id)
        .options(
            selectinload(InferenceDeployment.node),
            selectinload(InferenceDeployment.model),
            selectinload(InferenceDeployment.replica),
        )
    )
    if not deployment:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_DEPLOYMENT_NOT_FOUND"})
    before = deployment.status
    try:
        agent_result = await NodeAgentClient(deployment.node).get_deployment(deployment.id)
    except AgentClientError as exc:
        deployment.status = "degraded"
        deployment.error_code = exc.code
        deployment.error_summary = exc.message
        deployment.version += 1
        await db.commit()
        raise _deployment_http_error(exc) from exc

    if agent_result.status == "running" and deployment.replica:
        try:
            target = target_for_replica(deployment.model, deployment.replica)
            healthy = await backend_for_model(deployment.model).health_check(target)
        except Exception:
            healthy = False
        deployment.replica.health_status = "healthy" if healthy else "unhealthy"
        deployment.replica.last_health_checked_at = datetime.now(UTC)
        deployment.replica.version += 1
        deployment.status = "running" if healthy else "provisioning"
        deployment.error_code = None
        deployment.error_summary = None
    elif agent_result.status in {"exited", "stopped"}:
        deployment.status = "failed" if agent_result.exit_code else "stopped"
        if deployment.replica:
            deployment.replica.health_status = "unhealthy"
            deployment.replica.enabled = False
            deployment.replica.version += 1
    elif agent_result.status == "absent":
        deployment.status = "failed"
        deployment.error_code = "AGENT_DEPLOYMENT_MISSING"
        deployment.error_summary = "节点上找不到对应 vLLM 容器"
    else:
        deployment.status = "provisioning"
    deployment.version += 1
    if deployment.status != before:
        add_audit(
            db,
            actor_type="admin",
            actor_id=admin.id,
            action="inference_deployment.synced",
            object_type="inference_deployment",
            object_id=deployment.id,
            summary={"before": before, "after": deployment.status},
            request_id=request_id,
        )
    await db.commit()
    await db.refresh(deployment)
    return deployment


async def stop_deployment(
    db: AsyncSession,
    *,
    deployment_id: str,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceDeployment:
    deployment = await db.scalar(
        select(InferenceDeployment)
        .where(InferenceDeployment.id == deployment_id)
        .options(
            selectinload(InferenceDeployment.node),
            selectinload(InferenceDeployment.replica),
        )
    )
    if not deployment:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_DEPLOYMENT_NOT_FOUND"})
    try:
        await NodeAgentClient(deployment.node).remove_deployment(deployment.id)
    except AgentClientError as exc:
        raise _deployment_http_error(exc) from exc
    deployment.status = "stopped"
    deployment.stopped_at = datetime.now(UTC)
    deployment.error_code = None
    deployment.error_summary = None
    deployment.version += 1
    if deployment.replica:
        deployment.replica.enabled = False
        deployment.replica.health_status = "unknown"
        deployment.replica.version += 1
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_deployment.stopped",
        object_type="inference_deployment",
        object_id=deployment.id,
        summary={"node_id": deployment.node_id},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(deployment)
    return deployment
