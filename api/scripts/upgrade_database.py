"""Safely baseline recognized pre-Alembic Open Compute System databases, then upgrade."""

import asyncio
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.db.session import engine  # noqa: E402

INITIAL_REVISION = "3edf12b7c297"
OUTBOX_REVISION = "65f1010f9f45"
HARDENED_REVISION = "9a8b7c6d5e4f"
CORE_TABLES = {
    "admin_users",
    "audit_logs",
    "instances",
    "instance_tasks",
    "leads",
    "orders",
    "price_versions",
    "resource_providers",
    "skus",
    "users",
}


async def detect_baseline() -> str | None:
    async with engine.connect() as connection:
        def inspect_schema(sync_connection) -> str | None:
            inspector = inspect(sync_connection)
            tables = set(inspector.get_table_names())
            if "alembic_version" in tables:
                version = sync_connection.execute(
                    sa.text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar_one_or_none()
                if version:
                    return None
                tables.remove("alembic_version")
            if not tables:
                return None
            if not CORE_TABLES.issubset(tables):
                missing = ", ".join(sorted(CORE_TABLES - tables))
                raise RuntimeError(f"Unrecognized database schema; missing tables: {missing}")
            task_columns = {column["name"] for column in inspector.get_columns("instance_tasks")}
            hardened_columns = {"actor_id", "operation", "request_hash", "lease_expires_at"}
            has_outbox = "outbox_events" in tables
            has_wallet = "wallet_transactions" in tables
            if has_wallet and hardened_columns.issubset(task_columns):
                return HARDENED_REVISION
            if hardened_columns.intersection(task_columns):
                raise RuntimeError("Database appears partially migrated; refusing to stamp it")
            if has_wallet:
                wallet_rows = sync_connection.execute(
                    sa.text("SELECT COUNT(*) FROM wallet_transactions")
                ).scalar_one()
                if wallet_rows:
                    raise RuntimeError(
                        "Pre-migration wallet table contains data; refusing automatic baseline"
                    )
            return OUTBOX_REVISION if has_outbox else INITIAL_REVISION

        return await connection.run_sync(inspect_schema)


def alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def main() -> None:
    baseline = asyncio.run(detect_baseline())
    asyncio.run(engine.dispose())
    config = alembic_config()
    if baseline:
        print(f"Recognized pre-Alembic Open Compute System schema; baselining at {baseline}")
        command.stamp(config, baseline)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
