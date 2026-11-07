"""add inference nodes and vLLM deployments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-26 01:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inference_nodes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("agent_url", sa.String(length=240), nullable=False),
        sa.Column("agent_token_env_var", sa.String(length=120), nullable=False),
        sa.Column("runtime_credential_env_var", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("docker_version", sa.String(length=80), nullable=True),
        sa.Column("gpu_summary", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_url"),
    )
    op.create_index("ix_inference_nodes_status", "inference_nodes", ["status"])

    op.create_table(
        "inference_deployments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.String(length=32), nullable=False),
        sa.Column("replica_id", sa.String(length=32), nullable=True),
        sa.Column("model_source_id", sa.String(length=160), nullable=False),
        sa.Column("served_model_name", sa.String(length=120), nullable=False),
        sa.Column("image", sa.String(length=240), nullable=True),
        sa.Column("gpu_device_ids", sa.JSON(), nullable=False),
        sa.Column("tensor_parallel_size", sa.Integer(), nullable=False),
        sa.Column("host_port", sa.Integer(), nullable=False),
        sa.Column("max_model_len", sa.Integer(), nullable=True),
        sa.Column("gpu_memory_utilization_milli", sa.Integer(), nullable=False),
        sa.Column("huggingface_token_env_var", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("endpoint", sa.String(length=240), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.String(length=240), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tensor_parallel_size > 0",
            name="ck_inference_deployments_tp_positive",
        ),
        sa.CheckConstraint(
            "host_port >= 1024 AND host_port <= 65535",
            name="ck_inference_deployments_port_range",
        ),
        sa.CheckConstraint(
            "gpu_memory_utilization_milli >= 100 "
            "AND gpu_memory_utilization_milli <= 980",
            name="ck_inference_deployments_memory_utilization",
        ),
        sa.ForeignKeyConstraint(["model_id"], ["inference_models.id"]),
        sa.ForeignKeyConstraint(["node_id"], ["inference_nodes.id"]),
        sa.ForeignKeyConstraint(["replica_id"], ["inference_replicas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_inference_deployments_actor_idempotency",
        ),
        sa.UniqueConstraint("replica_id"),
    )
    op.create_index(
        "ix_inference_deployments_created_by",
        "inference_deployments",
        ["created_by"],
    )
    op.create_index(
        "ix_inference_deployments_model_id",
        "inference_deployments",
        ["model_id"],
    )
    op.create_index(
        "ix_inference_deployments_node_id",
        "inference_deployments",
        ["node_id"],
    )
    op.create_index(
        "ix_inference_deployments_status",
        "inference_deployments",
        ["status"],
    )
    op.create_index(
        "ix_inference_deployments_node_status",
        "inference_deployments",
        ["node_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("inference_deployments")
    op.drop_table("inference_nodes")
