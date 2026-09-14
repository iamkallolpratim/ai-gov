"""Audit log read schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, Field

from app.models.enums import ActorType, AuditAction
from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: uuid.UUID
    resource_type: str = Field(examples=["ai_system"])
    resource_id: uuid.UUID | None
    action: AuditAction = Field(examples=["update"])
    actor_id: uuid.UUID | None
    actor_email: str | None = Field(examples=["risk@aigov.example.com"])
    actor_type: ActorType = Field(
        examples=["user"],
        description="`system` marks an action taken while authentication was disabled.",
    )
    actor_label: str = Field(examples=["system"])
    request_id: str | None
    ip_address: str | None = Field(examples=["203.0.113.10"])
    user_agent: str | None
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    context: dict[str, Any]
    created_at: datetime


class AuditLogFilters(BaseModel):
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    action: AuditAction | None = None
    actor_id: uuid.UUID | None = None
    actor_type: ActorType | None = None
    request_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


def audit_filters(
    resource_type: Annotated[str | None, Query(description="e.g. ai_system, policy")] = None,
    resource_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
    actor_type: Annotated[
        ActorType | None, Query(description="Filter to actions taken without authentication")
    ] = None,
    request_id: Annotated[str | None, Query(description="Trace one request end to end")] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
) -> AuditLogFilters:
    return AuditLogFilters(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        actor_id=actor_id,
        actor_type=actor_type,
        request_id=request_id,
        since=since,
        until=until,
    )
