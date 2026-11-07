"""harden transactions, task recovery, and scoped idempotency

Revision ID: 9a8b7c6d5e4f
Revises: 65f1010f9f45
Create Date: 2026-08-24 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a8b7c6d5e4f"
down_revision: str | Sequence[str] | None = "65f1010f9f45"
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
        batch.create_check_constraint("users_balance_nonnegative", "balance_cents >= 0")

    with op.batch_alter_table("skus", naming_convention=NAMING_CONVENTION) as batch:
        batch.create_check_constraint("skus_inventory_total_nonnegative", "inventory_total >= 0")
        batch.create_check_constraint(
            "skus_inventory_available_nonnegative", "inventory_available >= 0"
        )
        batch.create_check_constraint(
            "skus_inventory_reserved_nonnegative", "inventory_reserved >= 0"
        )
        batch.create_check_constraint(
            "skus_inventory_within_total",
            "inventory_available + inventory_reserved <= inventory_total",
        )

    with op.batch_alter_table("orders", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("uq_orders_idempotency_key", type_="unique")
        batch.create_unique_constraint(
            "uq_orders_user_idempotency", ["user_id", "idempotency_key"]
        )
        batch.create_check_constraint("orders_amount_positive", "amount_cents > 0")
        batch.create_index("ix_orders_status_created_at", ["status", "created_at"])

    with op.batch_alter_table("instance_tasks", naming_convention=NAMING_CONVENTION) as batch:
        batch.add_column(sa.Column("actor_id", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("operation", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("request_hash", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("previous_instance_status", sa.String(length=24), nullable=True)
        )

    op.execute(
        sa.text(
            "UPDATE instance_tasks SET "
            "actor_id = (SELECT user_id FROM instances "
            "WHERE instances.id = instance_tasks.instance_id), "
            "operation = 'legacy.' || id, "
            "request_hash = '0000000000000000000000000000000000000000000000000000000000000000', "
            "previous_instance_status = CASE action "
            "WHEN 'start' THEN 'stopped' WHEN 'stop' THEN 'running' "
            "WHEN 'release' THEN 'stopped' ELSE 'pending' END"
        )
    )

    with op.batch_alter_table("instance_tasks", naming_convention=NAMING_CONVENTION) as batch:
        batch.alter_column("actor_id", existing_type=sa.String(length=32), nullable=False)
        batch.alter_column("operation", existing_type=sa.String(length=120), nullable=False)
        batch.alter_column("request_hash", existing_type=sa.String(length=64), nullable=False)
        batch.drop_constraint("uq_task_idempotency", type_="unique")
        batch.create_unique_constraint(
            "uq_task_actor_operation_key", ["actor_id", "operation", "idempotency_key"]
        )
        batch.create_check_constraint("tasks_progress_range", "progress >= 0 AND progress <= 100")
        batch.create_index("ix_instance_tasks_actor_id", ["actor_id"])
        batch.create_index("ix_tasks_lease_status", ["status", "lease_expires_at"])

    inspector = sa.inspect(op.get_bind())
    if "wallet_transactions" not in inspector.get_table_names():
        op.create_table(
            "wallet_transactions",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("order_id", sa.String(length=32), nullable=True),
            sa.Column("transaction_type", sa.String(length=24), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("balance_after_cents", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=160), nullable=False),
            sa.Column("description", sa.String(length=240), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("amount_cents != 0", name="ck_wallet_amount_nonzero"),
            sa.CheckConstraint(
                "balance_after_cents >= 0", name="ck_wallet_balance_nonnegative"
            ),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "idempotency_key", name="uq_wallet_user_idempotency"
            ),
        )
        op.create_index(
            "ix_wallet_transactions_order_id", "wallet_transactions", ["order_id"]
        )
        op.create_index(
            "ix_wallet_transactions_user_id", "wallet_transactions", ["user_id"]
        )
        op.create_index(
            "ix_wallet_user_created_at", "wallet_transactions", ["user_id", "created_at"]
        )

    with op.batch_alter_table("outbox_events") as batch:
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_outbox_ready", ["status", "available_at"])


def downgrade() -> None:
    with op.batch_alter_table("outbox_events") as batch:
        batch.drop_index("ix_outbox_ready")
        batch.drop_column("lease_expires_at")

    op.drop_index("ix_wallet_user_created_at", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_user_id", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_order_id", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")

    with op.batch_alter_table("instance_tasks", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_index("ix_tasks_lease_status")
        batch.drop_index("ix_instance_tasks_actor_id")
        batch.drop_constraint("tasks_progress_range", type_="check")
        batch.drop_constraint("uq_task_actor_operation_key", type_="unique")
        batch.create_unique_constraint("uq_task_idempotency", ["idempotency_key"])
        batch.drop_column("previous_instance_status")
        batch.drop_column("lease_expires_at")
        batch.drop_column("attempt_count")
        batch.drop_column("request_hash")
        batch.drop_column("operation")
        batch.drop_column("actor_id")

    with op.batch_alter_table("orders", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_index("ix_orders_status_created_at")
        batch.drop_constraint("orders_amount_positive", type_="check")
        batch.drop_constraint("uq_orders_user_idempotency", type_="unique")
        batch.create_unique_constraint("uq_orders_idempotency_key", ["idempotency_key"])

    with op.batch_alter_table("skus", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("skus_inventory_within_total", type_="check")
        batch.drop_constraint("skus_inventory_reserved_nonnegative", type_="check")
        batch.drop_constraint("skus_inventory_available_nonnegative", type_="check")
        batch.drop_constraint("skus_inventory_total_nonnegative", type_="check")

    with op.batch_alter_table("users", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("users_balance_nonnegative", type_="check")
