"""Create the first production super-admin without embedding credentials in images or code."""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import func, select

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import AdminUser  # noqa: E402


async def main() -> None:
    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    display_name = os.environ.get("BOOTSTRAP_ADMIN_DISPLAY_NAME", "平台管理员").strip()
    if len(username) < 3 or len(display_name) < 2:
        raise RuntimeError("Bootstrap admin username or display name is invalid")
    if len(password) < 12 or not any(char.isalpha() for char in password) or not any(
        char.isdigit() for char in password
    ):
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_PASSWORD must be 12+ characters with letters and digits"
        )
    async with SessionLocal() as db:
        existing = await db.scalar(select(func.count(AdminUser.id)))
        if existing:
            raise RuntimeError(
                "Admin users already exist; bootstrap is intentionally one-time only"
            )
        db.add(
            AdminUser(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role="super_admin",
                mfa_enabled=True,
            )
        )
        await db.commit()
    await engine.dispose()
    print(f"Created initial admin account: {username}")


if __name__ == "__main__":
    asyncio.run(main())
