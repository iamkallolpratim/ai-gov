"""Structured logging with correlation-id injection."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings
from app.core.context import get_actor_email, get_actor_id, get_request_id


def _add_request_context(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach the request fingerprint to every line, so logs are joinable."""
    if request_id := get_request_id():
        event_dict["request_id"] = request_id
    if actor := get_actor_id():
        event_dict["actor_id"] = actor
    if actor_email := get_actor_email():
        event_dict["actor_email"] = actor_email
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_request_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if settings.LOG_JSON
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
