"""Celery tasks must be bound to the application's Celery app on *every* thread.

`@shared_task` resolves its app through Celery's thread-local "current app", and
`Celery(...)` only makes itself current on the thread that constructs it. FastAPI runs
sync endpoints on a threadpool, so the evidence endpoint queued correctly on the thread
that first imported the Celery app and, on every other thread, bound to Celery's built-in
`default` app — no broker configured, fallback `amqp://localhost:5672`, and
`[Errno 111] Connection refused`. The bug looked intermittent and was misdiagnosed as a
transient Redis outage.

Each check resolves the task on a freshly spawned thread, which is exactly where the bug
lived. Nothing is published to a broker.
"""

from __future__ import annotations

import threading

import pytest

import app.workers.tasks as tasks_module
from app.core.config import settings

TASK_NAMES = sorted(
    name
    for name, obj in vars(tasks_module).items()
    if hasattr(obj, "delay") and hasattr(obj, "name") and obj.name.startswith("app.workers.")
)


def resolve_on_fresh_thread(task) -> tuple[str, str | None]:
    result: dict[str, object] = {}

    def probe() -> None:
        try:
            result["main"] = task.app.main
            result["broker"] = task.app.conf.broker_url
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            result["error"] = exc

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    assert "error" not in result, result.get("error")
    return str(result["main"]), result["broker"]  # type: ignore[return-value]


def test_tasks_were_discovered():
    assert "generate_evidence_package" in TASK_NAMES, TASK_NAMES


@pytest.mark.parametrize("name", TASK_NAMES)
def test_task_binds_to_the_application_app_on_any_thread(name: str):
    main, broker = resolve_on_fresh_thread(getattr(tasks_module, name))
    assert main == "aigov", f"{name} resolved to Celery app {main!r} on a worker thread"
    assert broker == settings.celery_broker


def test_default_app_is_the_application_app_on_any_thread():
    """Guards future `@shared_task` usage, not just the tasks that exist today."""
    from celery import current_app

    result: dict[str, str] = {}
    thread = threading.Thread(target=lambda: result.update(main=current_app.main))
    thread.start()
    thread.join()
    assert result["main"] == "aigov"
