import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path("/tmp/open-compute-system-api-test.db")
test_database_url = os.environ.get("TEST_DATABASE_URL")
if test_database_url:
    os.environ["DATABASE_URL"] = test_database_url
else:
    if TEST_DB.exists():
        TEST_DB.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ["APP_ENV"] = "test"
os.environ["MOCK_PROVIDER_DELAY_SECONDS"] = "0.02"
os.environ["DEMO_SEED_ENABLED"] = "true"

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
