"""add real inference endpoint configuration and key policies

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inference_replicas") as batch:
        batch.add_column(
            sa.Column("upstream_model", sa.String(length=160), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("credential_env_var", sa.String(length=120), nullable=True))
        batch.add_column(
            sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120")
        )
        batch.add_column(sa.Column("capacity_tpm", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(
            sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_check_constraint(
            "inference_replicas_timeout_positive", "timeout_seconds > 0"
        )
        batch.create_check_constraint(
            "inference_replicas_capacity_positive",
            "capacity_tpm IS NULL OR capacity_tpm > 0",
        )

    with op.batch_alter_table("api_keys") as batch:
        batch.add_column(
            sa.Column("tpm_limit", sa.Integer(), nullable=False, server_default="100000")
        )
        batch.add_column(
            sa.Column("allowed_models", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.create_check_constraint("api_keys_tpm_positive", "tpm_limit > 0")


def downgrade() -> None:
    with op.batch_alter_table("api_keys") as batch:
        batch.drop_constraint("api_keys_tpm_positive", type_="check")
        batch.drop_column("allowed_models")
        batch.drop_column("tpm_limit")

    with op.batch_alter_table("inference_replicas") as batch:
        batch.drop_constraint("inference_replicas_capacity_positive", type_="check")
        batch.drop_constraint("inference_replicas_timeout_positive", type_="check")
        batch.drop_column("last_health_checked_at")
        batch.drop_column("version")
        batch.drop_column("capacity_tpm")
        batch.drop_column("timeout_seconds")
        batch.drop_column("credential_env_var")
        batch.drop_column("upstream_model")
