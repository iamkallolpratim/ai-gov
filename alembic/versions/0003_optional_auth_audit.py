"""Optional authentication: system principal and a richer audit trail.

Adds the `is_system` flag used by the synthetic principal that serves requests when
AUTH_DISABLED is set, and extends `audit_logs` with the actor type, request
fingerprint (id, IP, user agent) and before/after values.

`entity_*` columns are renamed to `resource_*` to match the API vocabulary. The
append-only triggers are dropped and recreated around the change, because they reject
the DDL-adjacent writes otherwise.

Revision ID: 0003_optional_auth
Revises: 0002_reach_regions
Create Date: 2026-08-25 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_optional_auth"
down_revision: str | None = "0002_reach_regions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())

ACTOR_TYPE = sa.Enum("user", "system", name="actor_type", native_enum=False, length=16)


def upgrade() -> None:
    # --- system principal ---
    op.add_column(
        "users",
        sa.Column(
            "is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.alter_column("users", "is_system", server_default=None)

    # --- audit trail ---
    # The append-only trigger blocks UPDATE, which the backfill below needs.
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;")

    op.alter_column("audit_logs", "entity_type", new_column_name="resource_type")
    op.alter_column("audit_logs", "entity_id", new_column_name="resource_id")
    op.alter_column("audit_logs", "correlation_id", new_column_name="request_id")
    op.alter_column("audit_logs", "changes", new_column_name="new_values")

    op.add_column(
        "audit_logs",
        sa.Column("actor_type", ACTOR_TYPE, nullable=False, server_default="user"),
    )
    op.add_column(
        "audit_logs",
        sa.Column("actor_label", sa.String(length=64), nullable=False, server_default="system"),
    )
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("old_values", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    # Existing rows were all written by real users.
    op.execute(
        "UPDATE audit_logs SET actor_label = COALESCE(actor_id::text, 'system') "
        "WHERE actor_label = 'system'"
    )

    for column in ("actor_type", "actor_label", "old_values"):
        op.alter_column("audit_logs", column, server_default=None)

    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id", "created_at"]
    )
    op.create_index("ix_audit_logs_actor_time", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_actor_type", "audit_logs", ["actor_type"])

    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION reject_mutation_audit_logs();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;")

    op.drop_index("ix_audit_logs_actor_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_time", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")

    op.drop_column("audit_logs", "old_values")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "actor_label")
    op.drop_column("audit_logs", "actor_type")

    op.alter_column("audit_logs", "new_values", new_column_name="changes")
    op.alter_column("audit_logs", "request_id", new_column_name="correlation_id")
    op.alter_column("audit_logs", "resource_id", new_column_name="entity_id")
    op.alter_column("audit_logs", "resource_type", new_column_name="entity_type")

    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id", "created_at"])
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION reject_mutation_audit_logs();
        """
    )
    op.drop_column("users", "is_system")
