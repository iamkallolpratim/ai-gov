"""Append-only audit trail writer.

Works identically in both authentication modes. When `AUTH_DISABLED` is set the actor is
the system principal, recorded with `actor_type=system` and the label `system`, so an
operator reading the trail can always tell which actions came from an unauthenticated
deployment.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import get_client_ip, get_request_id, get_user_agent
from app.core.principal import SYSTEM_ACTOR_LABEL
from app.models.audit import AuditLog
from app.models.enums import ActorType, AuditAction
from app.models.user import User


def record_audit(
    db: Session,
    *,
    resource_type: str,
    action: AuditAction,
    resource_id: uuid.UUID | None = None,
    actor: User | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    # Previous parameter names.
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    """Write one immutable audit entry.

    The request fingerprint (id, client IP, user agent) is pulled from the request
    context rather than passed in, so services do not need to know about HTTP.
    """
    resource_type = resource_type or entity_type or "unknown"
    resource_id = resource_id if resource_id is not None else entity_id
    new_values = new_values if new_values is not None else changes

    is_system_actor = bool(actor is not None and actor.is_system)
    entry = AuditLog(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        actor_type=ActorType.SYSTEM if (is_system_actor or actor is None) else ActorType.USER,
        actor_label=SYSTEM_ACTOR_LABEL if (is_system_actor or actor is None) else str(actor.id),
        request_id=get_request_id(),
        ip_address=get_client_ip(),
        user_agent=(get_user_agent() or None),
        old_values=old_values or {},
        new_values=new_values or {},
        context=context or {},
    )
    db.add(entry)
    return entry


def split_diff(diff: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split an InventoryService-style ``{field: [old, new]}`` diff into two documents."""
    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    for field, change in diff.items():
        if isinstance(change, list) and len(change) == 2:
            old[field], new[field] = change
        elif isinstance(change, dict):
            nested_old, nested_new = split_diff(change)
            if nested_old or nested_new:
                old[field], new[field] = nested_old, nested_new
        else:
            new[field] = change
    return old, new
