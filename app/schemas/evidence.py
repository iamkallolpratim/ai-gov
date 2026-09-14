from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import EvidenceStatus
from app.schemas.common import ORMModel


class EvidenceGenerateRequest(BaseModel):
    jurisdictions: list[str] | None = Field(
        default=None,
        description="Default = all jurisdictions currently applicable to the system.",
        examples=[["EU", "IN"]],
    )
    include_policy_checks: bool = True
    include_history: bool = False
    refresh_checks: bool = Field(
        default=False, description="Re-run policy checks before packaging."
    )
    notes: str | None = Field(default=None, max_length=2000)


class EvidencePackageRead(ORMModel):
    id: uuid.UUID
    ai_system_id: uuid.UUID
    jurisdictions: list[str]
    status: EvidenceStatus
    task_id: str | None
    file_url: str | None
    json_url: str | None
    checksum_sha256: str | None
    error_message: str | None
    summary: dict[str, Any]
    generated_at: datetime | None
    generated_by_id: uuid.UUID | None
    created_at: datetime
    #: Last queue, retry or worker start. Staleness is measured from this.
    updated_at: datetime


class EvidenceAcceptedResponse(BaseModel):
    package_id: uuid.UUID
    task_id: str | None
    status: EvidenceStatus = EvidenceStatus.PENDING
    poll_url: str
