"""Celery application."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

celery_app = Celery(
    "aigov",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.workers.tasks"],
)

# `Celery(...)` only marks itself "current" on the thread that constructs it. FastAPI runs
# sync endpoints on a threadpool, so on every other thread Celery fell back to its built-in
# `default` app — no broker, fallback amqp://localhost:5672, `Connection refused`. Making
# this the default app closes that on all threads; tasks.py also binds explicitly.
celery_app.set_default()

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    result_expires=60 * 60 * 24,
    task_default_queue="aigov",
    beat_schedule={
        "refresh-dashboard-cache": {
            "task": "app.workers.tasks.refresh_dashboard_cache",
            "schedule": 300.0,
        },
        "expire-stale-evidence-packages": {
            "task": "app.workers.tasks.expire_stale_evidence_packages",
            "schedule": 300.0,
        },
    },
)
