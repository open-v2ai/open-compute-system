"""add email login identities

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-26 04:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    checks = {constraint["name"] for constraint in inspector.get_check_constraints("users")}

    if (
        columns["phone"]["nullable"] is False
        or "email" not in columns
        or "ck_users_has_identity" not in checks
    ):
        with op.batch_alter_table("users") as batch_op:
            if columns["phone"]["nullable"] is False:
                batch_op.alter_column(
                    "phone",
                    existing_type=sa.String(length=24),
                    existing_nullable=False,
                    nullable=True,
                )
            if "email" not in columns:
                batch_op.add_column(sa.Column("email", sa.String(length=254), nullable=True))
            if "ck_users_has_identity" not in checks:
                batch_op.create_check_constraint(
                    "ck_users_has_identity",
                    "phone IS NOT NULL OR email IS NOT NULL",
                )

    inspector = sa.inspect(connection)
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" not in indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    connection = op.get_bind()
    email_only_users = connection.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE phone IS NULL")
    ).scalar_one()
    if email_only_users:
        raise RuntimeError("Cannot downgrade while email-only users exist")

    op.drop_index("ix_users_email", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_has_identity", type_="check")
        batch_op.drop_column("email")
        batch_op.alter_column(
            "phone",
            existing_type=sa.String(length=24),
            existing_nullable=True,
            nullable=False,
        )
