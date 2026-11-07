"""add auto router configuration and routing telemetry

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-26 04:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auto_router_configs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("virtual_model_id", sa.String(length=32), nullable=False),
        sa.Column("classifier_model_id", sa.String(length=32), nullable=False),
        sa.Column("simple_model_id", sa.String(length=32), nullable=False),
        sa.Column("complex_model_id", sa.String(length=32), nullable=False),
        sa.Column("fallback_tier", sa.String(length=16), nullable=False),
        sa.Column("classifier_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "classifier_timeout_seconds > 0 AND classifier_timeout_seconds <= 30",
            name="ck_auto_router_classifier_timeout",
        ),
        sa.CheckConstraint(
            "fallback_tier IN ('simple', 'complex')",
            name="ck_auto_router_fallback_tier",
        ),
        sa.ForeignKeyConstraint(["classifier_model_id"], ["inference_models.id"]),
        sa.ForeignKeyConstraint(["complex_model_id"], ["inference_models.id"]),
        sa.ForeignKeyConstraint(["simple_model_id"], ["inference_models.id"]),
        sa.ForeignKeyConstraint(["virtual_model_id"], ["inference_models.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("virtual_model_id"),
    )
    op.create_index(
        "ix_auto_router_configs_virtual_model_id",
        "auto_router_configs",
        ["virtual_model_id"],
        unique=True,
    )
    op.create_index(
        "ix_auto_router_configs_classifier_model_id",
        "auto_router_configs",
        ["classifier_model_id"],
    )
    op.create_index(
        "ix_auto_router_configs_simple_model_id",
        "auto_router_configs",
        ["simple_model_id"],
    )
    op.create_index(
        "ix_auto_router_configs_complex_model_id",
        "auto_router_configs",
        ["complex_model_id"],
    )

    with op.batch_alter_table("usage_events") as batch:
        batch.add_column(sa.Column("routed_model_slug", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("routing_tier", sa.String(length=16), nullable=True))
        batch.add_column(
            sa.Column("routing_decision_source", sa.String(length=32), nullable=True)
        )
        batch.add_column(
            sa.Column("classifier_model_slug", sa.String(length=120), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "classifier_latency_ms",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_events") as batch:
        batch.drop_column("classifier_latency_ms")
        batch.drop_column("classifier_model_slug")
        batch.drop_column("routing_decision_source")
        batch.drop_column("routing_tier")
        batch.drop_column("routed_model_slug")
    op.drop_table("auto_router_configs")
