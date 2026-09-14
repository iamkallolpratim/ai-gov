"""Add reach signals (offering, service accessibility, content accessibility).

The jurisdiction engine distinguishes where a system is *deployed* from where it is
*offered*, where it can be *reached*, and where its *output* can be viewed. Existing rows
default to an empty list, which keeps their current applicability unchanged.

Revision ID: 0002_reach_regions
Revises: 0001_initial
Create Date: 2026-02-01 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_reach_regions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
NEW_COLUMNS = (
    "offered_in_regions",
    "service_accessible_regions",
    "content_accessible_regions",
)


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column(
            "system_metadata",
            sa.Column(column, JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        )
        # The default exists only to backfill; the application always sends a value.
        op.alter_column("system_metadata", column, server_default=None)


def downgrade() -> None:
    for column in NEW_COLUMNS:
        op.drop_column("system_metadata", column)
