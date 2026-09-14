"""Shared helpers for building EU policy rows in tests."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.seed import POLICIES
from app.models.policy import Policy

POLICY_DIR = Path(__file__).resolve().parents[1] / "policies"


def make_policies(db: Session, *, keys: set[str] | None = None) -> dict[str, Policy]:
    """Insert the seeded EU policies, with their real Rego attached."""
    created: dict[str, Policy] = {}
    for spec in POLICIES:
        if spec["jurisdiction_code"] != "EU":
            continue
        if keys and spec["key"] not in keys:
            continue
        data = dict(spec)
        rego_file = data.pop("rego_file")
        rego_path = POLICY_DIR / rego_file
        policy = Policy(
            id=uuid.uuid4(),
            **data,
            rego_code=rego_path.read_text() if rego_path.exists() else None,
            is_active=True,
            is_deleted=False,
        )
        db.add(policy)
        created[policy.key] = policy
    db.flush()
    return created
