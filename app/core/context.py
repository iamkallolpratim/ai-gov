"""Request-scoped context: request id, actor, and client fingerprint.

Held in contextvars so any layer — a service deep in the call stack, a log processor,
the audit writer — can reach the current request's identity without threading it
through every signature.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("actor_id", default=None)
_actor_email: ContextVar[str | None] = ContextVar("actor_email", default=None)
_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
_user_agent: ContextVar[str | None] = ContextVar("user_agent", default=None)


def new_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(value: str | None) -> str:
    rid = value or new_request_id()
    _request_id.set(rid)
    return rid


def get_request_id() -> str | None:
    return _request_id.get()


# Correlation id is the same value under its previous name, kept so existing callers
# and the X-Correlation-ID response header keep working.
set_correlation_id = set_request_id
get_correlation_id = get_request_id
new_correlation_id = new_request_id


def set_actor(user_id: str | None, email: str | None = None) -> None:
    _actor_id.set(user_id)
    _actor_email.set(email)


def set_actor_id(value: str | None) -> None:
    _actor_id.set(value)


def get_actor_id() -> str | None:
    return _actor_id.get()


def get_actor_email() -> str | None:
    return _actor_email.get()


def set_client_info(ip: str | None, user_agent: str | None) -> None:
    _client_ip.set(ip)
    _user_agent.set(user_agent)


def get_client_ip() -> str | None:
    return _client_ip.get()


def get_user_agent() -> str | None:
    return _user_agent.get()


def reset_context() -> None:
    """Clear everything. Used by workers between tasks."""
    _request_id.set(None)
    _actor_id.set(None)
    _actor_email.set(None)
    _client_ip.set(None)
    _user_agent.set(None)
