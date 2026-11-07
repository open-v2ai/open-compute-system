import asyncio
from types import SimpleNamespace

import pytest

from app.workers import celery_app as worker


def test_each_worker_task_disposes_connections_before_its_event_loop_closes(monkeypatch) -> None:
    task_loops = []
    cleanup_loops = []

    async def dispose() -> None:
        loop = asyncio.get_running_loop()
        assert not loop.is_closed()
        cleanup_loops.append(loop)

    monkeypatch.setattr(worker, "engine", SimpleNamespace(dispose=dispose))

    async def service(value: int) -> int:
        task_loops.append(asyncio.get_running_loop())
        return value

    assert worker.run_async_service(service(1)) == 1
    assert worker.run_async_service(service(2)) == 2
    assert task_loops[0] is not task_loops[1]
    assert cleanup_loops == task_loops
    assert all(loop.is_closed() for loop in task_loops)


def test_worker_failure_keeps_original_error_and_disposes_connections(monkeypatch) -> None:
    cleaned = []

    async def dispose() -> None:
        cleaned.append(True)

    async def failing_service() -> None:
        raise ValueError("service failure")

    monkeypatch.setattr(worker, "engine", SimpleNamespace(dispose=dispose))
    with pytest.raises(ValueError, match="service failure"):
        worker.run_async_service(failing_service())
    assert cleaned == [True]
