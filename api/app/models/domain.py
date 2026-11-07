from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("balance_cents >= 0", name="ck_users_balance_nonnegative"),
        CheckConstraint("phone IS NOT NULL OR email IS NOT NULL", name="ck_users_has_identity"),
        CheckConstraint(
            "inference_remainder_micros >= 0 AND inference_remainder_micros < 10000",
            name="ck_users_inference_remainder_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("usr"))
    phone: Mapped[str | None] = mapped_column(String(24), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(80), default="算力用户")
    balance_cents: Mapped[int] = mapped_column(Integer, default=200_000)
    inference_remainder_micros: Mapped[int] = mapped_column(Integer, default=0)
    real_name_status: Mapped[str] = mapped_column(String(24), default="unverified")
    status: Mapped[str] = mapped_column(String(24), default="active")


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("adm"))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(32), default="super_admin")
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="active")


class ResourceProvider(Base, TimestampMixin):
    __tablename__ = "resource_providers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("prv"))
    name: Mapped[str] = mapped_column(String(120))
    provider_type: Mapped[str] = mapped_column(String(24), default="owned")
    access_mode: Mapped[str] = mapped_column(String(24), default="mock")
    region: Mapped[str] = mapped_column(String(80))
    health_status: Mapped[str] = mapped_column(String(24), default="healthy")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SKU(Base, TimestampMixin):
    __tablename__ = "skus"
    __table_args__ = (
        CheckConstraint("inventory_total >= 0", name="ck_skus_inventory_total_nonnegative"),
        CheckConstraint(
            "inventory_available >= 0", name="ck_skus_inventory_available_nonnegative"
        ),
        CheckConstraint(
            "inventory_reserved >= 0", name="ck_skus_inventory_reserved_nonnegative"
        ),
        CheckConstraint(
            "inventory_available + inventory_reserved <= inventory_total",
            name="ck_skus_inventory_within_total",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sku"))
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("resource_providers.id"))
    name: Mapped[str] = mapped_column(String(120))
    gpu_model: Mapped[str] = mapped_column(String(80), index=True)
    gpu_memory_gb: Mapped[int] = mapped_column(Integer)
    gpu_count: Mapped[int] = mapped_column(Integer, default=1)
    vcpu: Mapped[int] = mapped_column(Integer)
    memory_gb: Mapped[int] = mapped_column(Integer)
    system_disk_gb: Mapped[int] = mapped_column(Integer, default=30)
    data_disk_gb: Mapped[int] = mapped_column(Integer, default=50)
    region: Mapped[str] = mapped_column(String(80), index=True)
    zone: Mapped[str] = mapped_column(String(80), default="A 区")
    cpu_vendor: Mapped[str] = mapped_column(String(40), default="Intel")
    price_hour_cents: Mapped[int] = mapped_column(Integer)
    price_day_cents: Mapped[int] = mapped_column(Integer)
    price_week_cents: Mapped[int] = mapped_column(Integer)
    price_month_cents: Mapped[int] = mapped_column(Integer)
    cost_hour_cents: Mapped[int] = mapped_column(Integer)
    inventory_total: Mapped[int] = mapped_column(Integer, default=0)
    inventory_available: Mapped[int] = mapped_column(Integer, default=0)
    inventory_reserved: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="published")
    tag: Mapped[str | None] = mapped_column(String(40))
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    provider: Mapped[ResourceProvider | None] = relationship()


class PriceVersion(Base, TimestampMixin):
    __tablename__ = "price_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("prc"))
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"), index=True)
    price_hour_cents: Mapped[int] = mapped_column(Integer)
    price_day_cents: Mapped[int] = mapped_column(Integer)
    price_week_cents: Mapped[int] = mapped_column(Integer)
    price_month_cents: Mapped[int] = mapped_column(Integer)
    cost_hour_cents: Mapped[int] = mapped_column(Integer)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str] = mapped_column(String(240), default="初始价格")
    created_by: Mapped[str] = mapped_column(String(32), default="system")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency"),
        CheckConstraint("amount_cents > 0", name="ck_orders_amount_positive"),
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ord"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"))
    order_type: Mapped[str] = mapped_column(String(24), default="instance")
    billing_mode: Mapped[str] = mapped_column(String(24), default="hourly")
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(128))

    sku: Mapped[SKU] = relationship()


class Instance(Base, TimestampMixin):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ins"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    name: Mapped[str] = mapped_column(String(80))
    image: Mapped[str] = mapped_column(String(120), default="PyTorch 2.7 · CUDA 12.8")
    billing_mode: Mapped[str] = mapped_column(String(24), default="hourly")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    provider_instance_id: Mapped[str | None] = mapped_column(String(100))
    ssh_host: Mapped[str | None] = mapped_column(String(160))
    ssh_port: Mapped[int | None] = mapped_column(Integer)
    jupyter_url: Mapped[str | None] = mapped_column(String(300))
    credential_hint: Mapped[str | None] = mapped_column(String(120))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sku: Mapped[SKU] = relationship()


class InstanceTask(Base, TimestampMixin):
    __tablename__ = "instance_tasks"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "operation", "idempotency_key", name="uq_task_actor_operation_key"
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_tasks_progress_range"),
        Index("ix_tasks_lease_status", "status", "lease_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("tsk"))
    instance_id: Mapped[str] = mapped_column(ForeignKey("instances.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    provider_task_id: Mapped[str | None] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(240))
    triggered_by: Mapped[str] = mapped_column(String(32), default="user")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previous_instance_status: Mapped[str | None] = mapped_column(String(24))


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_user_idempotency"),
        CheckConstraint("amount_cents != 0", name="ck_wallet_amount_nonzero"),
        CheckConstraint("balance_after_cents >= 0", name="ck_wallet_balance_nonnegative"),
        Index("ix_wallet_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("wtx"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(24))
    amount_cents: Mapped[int] = mapped_column(Integer)
    balance_after_cents: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lead(Base, TimestampMixin):
    """Retained for existing databases. Lead APIs and UI were removed from the product."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("lead"))
    lead_type: Mapped[str] = mapped_column(String(32))
    source_page: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(80))
    contact: Mapped[str] = mapped_column(String(80), index=True)
    organization: Mapped[str | None] = mapped_column(String(160))
    product: Mapped[str | None] = mapped_column(String(160))
    requirement: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(32), default="new")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    owner: Mapped[str | None] = mapped_column(String(80))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("aud"))
    actor_type: Mapped[str] = mapped_column(String(24))
    actor_id: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[str | None] = mapped_column(String(80))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[str] = mapped_column(String(24), default="succeeded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_ready", "status", "available_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("evt"))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(40))
    aggregate_id: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(240))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InferenceModel(Base, TimestampMixin):
    __tablename__ = "inference_models"
    __table_args__ = (
        CheckConstraint(
            "price_prompt_per_mtok_cents > 0", name="ck_inference_models_prompt_price"
        ),
        CheckConstraint(
            "price_completion_per_mtok_cents > 0",
            name="ck_inference_models_completion_price",
        ),
        CheckConstraint("cost_prompt_per_mtok_cents >= 0", name="ck_inference_models_prompt_cost"),
        CheckConstraint(
            "cost_completion_per_mtok_cents >= 0",
            name="ck_inference_models_completion_cost",
        ),
        CheckConstraint("context_length > 0", name="ck_inference_models_context"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("mdl"))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500), default="")
    context_length: Mapped[int] = mapped_column(Integer, default=8192)
    price_prompt_per_mtok_cents: Mapped[int] = mapped_column(Integer)
    price_completion_per_mtok_cents: Mapped[int] = mapped_column(Integer)
    cost_prompt_per_mtok_cents: Mapped[int] = mapped_column(Integer)
    cost_completion_per_mtok_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    backend_type: Mapped[str] = mapped_column(String(24), default="mock")
    version: Mapped[int] = mapped_column(Integer, default=1)

    replicas: Mapped[list[InferenceReplica]] = relationship(back_populates="model")
    router_config: Mapped[AutoRouterConfig | None] = relationship(
        back_populates="virtual_model",
        cascade="all, delete-orphan",
        foreign_keys="AutoRouterConfig.virtual_model_id",
        uselist=False,
    )

    @property
    def is_auto_router(self) -> bool:
        return self.backend_type == "auto_router"


class AutoRouterConfig(Base, TimestampMixin):
    __tablename__ = "auto_router_configs"
    __table_args__ = (
        CheckConstraint(
            "classifier_timeout_seconds > 0 AND classifier_timeout_seconds <= 30",
            name="ck_auto_router_classifier_timeout",
        ),
        CheckConstraint(
            "fallback_tier IN ('simple', 'complex')",
            name="ck_auto_router_fallback_tier",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("art"))
    virtual_model_id: Mapped[str] = mapped_column(
        ForeignKey("inference_models.id"), unique=True, index=True
    )
    classifier_model_id: Mapped[str] = mapped_column(
        ForeignKey("inference_models.id"), index=True
    )
    simple_model_id: Mapped[str] = mapped_column(ForeignKey("inference_models.id"), index=True)
    complex_model_id: Mapped[str] = mapped_column(ForeignKey("inference_models.id"), index=True)
    fallback_tier: Mapped[str] = mapped_column(String(16), default="complex")
    classifier_timeout_seconds: Mapped[int] = mapped_column(Integer, default=5)
    version: Mapped[int] = mapped_column(Integer, default=1)

    virtual_model: Mapped[InferenceModel] = relationship(
        back_populates="router_config",
        foreign_keys=[virtual_model_id],
    )


class InferenceReplica(Base, TimestampMixin):
    __tablename__ = "inference_replicas"
    __table_args__ = (
        UniqueConstraint("model_id", "label", name="uq_inference_replicas_model_label"),
        CheckConstraint("weight > 0", name="ck_inference_replicas_weight"),
        CheckConstraint("timeout_seconds > 0", name="ck_inference_replicas_timeout_positive"),
        CheckConstraint(
            "capacity_tpm IS NULL OR capacity_tpm > 0",
            name="ck_inference_replicas_capacity_positive",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("rpl"))
    model_id: Mapped[str] = mapped_column(ForeignKey("inference_models.id"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    endpoint: Mapped[str] = mapped_column(String(240), default="mock://local")
    upstream_model: Mapped[str] = mapped_column(String(160), default="")
    credential_env_var: Mapped[str | None] = mapped_column(String(120))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    capacity_tpm: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    health_status: Mapped[str] = mapped_column(String(24), default="healthy")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    fail_once: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[InferenceModel] = relationship(back_populates="replicas")


class InferenceNode(Base, TimestampMixin):
    __tablename__ = "inference_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("nod"))
    name: Mapped[str] = mapped_column(String(120))
    agent_url: Mapped[str] = mapped_column(String(240), unique=True)
    agent_token_env_var: Mapped[str] = mapped_column(String(120))
    runtime_credential_env_var: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    docker_version: Mapped[str | None] = mapped_column(String(80))
    gpu_summary: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InferenceDeployment(Base, TimestampMixin):
    __tablename__ = "inference_deployments"
    __table_args__ = (
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_inference_deployments_actor_idempotency",
        ),
        CheckConstraint("tensor_parallel_size > 0", name="ck_inference_deployments_tp_positive"),
        CheckConstraint(
            "host_port >= 1024 AND host_port <= 65535",
            name="ck_inference_deployments_port_range",
        ),
        CheckConstraint(
            "gpu_memory_utilization_milli >= 100 "
            "AND gpu_memory_utilization_milli <= 980",
            name="ck_inference_deployments_memory_utilization",
        ),
        Index("ix_inference_deployments_node_status", "node_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("dep"))
    created_by: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(ForeignKey("inference_models.id"), index=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("inference_nodes.id"), index=True)
    replica_id: Mapped[str | None] = mapped_column(
        ForeignKey("inference_replicas.id"), unique=True
    )
    model_source_id: Mapped[str] = mapped_column(String(160))
    served_model_name: Mapped[str] = mapped_column(String(120))
    image: Mapped[str | None] = mapped_column(String(240))
    gpu_device_ids: Mapped[list[int]] = mapped_column(JSON)
    tensor_parallel_size: Mapped[int] = mapped_column(Integer, default=1)
    host_port: Mapped[int] = mapped_column(Integer)
    max_model_len: Mapped[int | None] = mapped_column(Integer)
    gpu_memory_utilization_milli: Mapped[int] = mapped_column(Integer, default=900)
    huggingface_token_env_var: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    endpoint: Mapped[str | None] = mapped_column(String(240))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(Integer, default=1)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[InferenceModel] = relationship()
    node: Mapped[InferenceNode] = relationship()
    replica: Mapped[InferenceReplica | None] = relationship()

    @property
    def gpu_memory_utilization(self) -> float:
        return self.gpu_memory_utilization_milli / 1000


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_user_status", "user_id", "status"),
        CheckConstraint("tpm_limit > 0", name="ck_api_keys_tpm_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("key"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    credit_limit_cents: Mapped[int | None] = mapped_column(Integer)
    spent_cents: Mapped[int] = mapped_column(Integer, default=0)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=60)
    tpm_limit: Mapped[int] = mapped_column(Integer, default=100_000)
    allowed_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatConversation(Base, TimestampMixin):
    __tablename__ = "chat_conversations"
    __table_args__ = (Index("ix_chat_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cnv"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="新对话")
    model_slug: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="active")

    messages: Mapped[list[ChatMessage]] = relationship(back_populates="conversation")


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_conversation", "conversation_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("msg"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("chat_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usage_event_id: Mapped[str | None] = mapped_column(String(32))

    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_usage_events_request_id"),
        Index("ix_usage_events_user_created", "user_id", "created_at"),
        Index("ix_usage_events_model_created", "model_slug", "created_at"),
        CheckConstraint("prompt_tokens >= 0", name="ck_usage_prompt_tokens"),
        CheckConstraint("completion_tokens >= 0", name="ck_usage_completion_tokens"),
        CheckConstraint("cost_micros >= 0", name="ck_usage_cost_micros"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("usg"))
    request_id: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_conversations.id"), index=True
    )
    model_slug: Mapped[str] = mapped_column(String(120))
    routed_model_slug: Mapped[str | None] = mapped_column(String(120))
    routing_tier: Mapped[str | None] = mapped_column(String(16))
    routing_decision_source: Mapped[str | None] = mapped_column(String(32))
    classifier_model_slug: Mapped[str | None] = mapped_column(String(120))
    classifier_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    replica_label: Mapped[str | None] = mapped_column(String(80))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_micros: Mapped[int] = mapped_column(Integer, default=0)
    debit_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="succeeded")
    error_code: Mapped[str | None] = mapped_column(String(64))
    response_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
