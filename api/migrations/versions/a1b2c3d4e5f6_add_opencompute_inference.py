"""add OpenComputeSystem inference tables

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-08-25 00:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "9a8b7c6d5e4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    with op.batch_alter_table("users", naming_convention=NAMING_CONVENTION) as batch:
        batch.add_column(
            sa.Column(
                "inference_remainder_micros", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.create_check_constraint(
            "users_inference_remainder_range",
            "inference_remainder_micros >= 0 AND inference_remainder_micros < 10000",
        )

    op.create_table(
        "inference_models",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=False),
        sa.Column("price_prompt_per_mtok_cents", sa.Integer(), nullable=False),
        sa.Column("price_completion_per_mtok_cents", sa.Integer(), nullable=False),
        sa.Column("cost_prompt_per_mtok_cents", sa.Integer(), nullable=False),
        sa.Column("cost_completion_per_mtok_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("backend_type", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "price_prompt_per_mtok_cents > 0", name="ck_inference_models_prompt_price"
        ),
        sa.CheckConstraint(
            "price_completion_per_mtok_cents > 0",
            name="ck_inference_models_completion_price",
        ),
        sa.CheckConstraint(
            "cost_prompt_per_mtok_cents >= 0", name="ck_inference_models_prompt_cost"
        ),
        sa.CheckConstraint(
            "cost_completion_per_mtok_cents >= 0",
            name="ck_inference_models_completion_cost",
        ),
        sa.CheckConstraint("context_length > 0", name="ck_inference_models_context"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_inference_models_slug", "inference_models", ["slug"])
    op.create_index("ix_inference_models_status", "inference_models", ["status"])

    op.create_table(
        "inference_replicas",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("endpoint", sa.String(length=240), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("health_status", sa.String(length=24), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("fail_once", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weight > 0", name="ck_inference_replicas_weight"),
        sa.ForeignKeyConstraint(["model_id"], ["inference_models.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "label", name="uq_inference_replicas_model_label"),
    )
    op.create_index("ix_inference_replicas_model_id", "inference_replicas", ["model_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("credit_limit_cents", sa.Integer(), nullable=True),
        sa.Column("spent_cents", sa.Integer(), nullable=False),
        sa.Column("rpm_limit", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_status", "api_keys", ["status"])
    op.create_index("ix_api_keys_user_status", "api_keys", ["user_id", "status"])

    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_index(
        "ix_chat_conversations_user_updated", "chat_conversations", ["user_id", "updated_at"]
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("usage_event_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index(
        "ix_chat_messages_conversation", "chat_messages", ["conversation_id", "created_at"]
    )

    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("api_key_id", sa.String(length=32), nullable=True),
        sa.Column("conversation_id", sa.String(length=32), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("replica_label", sa.String(length=80), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.Integer(), nullable=False),
        sa.Column("debit_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("prompt_tokens >= 0", name="ck_usage_prompt_tokens"),
        sa.CheckConstraint("completion_tokens >= 0", name="ck_usage_completion_tokens"),
        sa.CheckConstraint("cost_micros >= 0", name="ck_usage_cost_micros"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_usage_events_request_id"),
    )
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])
    op.create_index("ix_usage_events_api_key_id", "usage_events", ["api_key_id"])
    op.create_index("ix_usage_events_conversation_id", "usage_events", ["conversation_id"])
    op.create_index("ix_usage_events_user_created", "usage_events", ["user_id", "created_at"])
    op.create_index("ix_usage_events_model_created", "usage_events", ["model_slug", "created_at"])


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
    op.drop_table("api_keys")
    op.drop_table("inference_replicas")
    op.drop_table("inference_models")
    with op.batch_alter_table("users", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("ck_users_inference_remainder_range", type_="check")
        batch.drop_column("inference_remainder_micros")
