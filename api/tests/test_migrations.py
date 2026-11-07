import os
import sqlite3
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def test_empty_sqlite_upgrade_and_replay_preserve_scoped_idempotency(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    env = {
        **os.environ,
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "scripts/upgrade_database.py"],
            cwd=API_ROOT, env=env, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert revision == "e5f6a7b8c9d0"
        indexes = connection.execute("PRAGMA index_list('orders')").fetchall()
        unique_columns = [
            [item[2] for item in connection.execute(f'PRAGMA index_info("{row[1]}")')]
            for row in indexes if row[2]
        ]
        assert ["user_id", "idempotency_key"] in unique_columns
        assert ["idempotency_key"] not in unique_columns
