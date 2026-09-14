"""Initial AI Governance Console schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())

USER_ROLE = sa.Enum("admin", "risk_officer", "viewer", name="user_role", native_enum=False, length=32)
SYSTEM_STATUS = sa.Enum(
    "draft", "active", "retired", name="system_status", native_enum=False, length=32
)
AUTONOMY = sa.Enum(
    "human_in_the_loop",
    "human_on_the_loop",
    "fully_autonomous",
    name="autonomy_level",
    native_enum=False,
    length=32,
)
RISK_TIER = sa.Enum(
    "prohibited", "high", "limited", "minimal", "unknown", name="risk_tier", native_enum=False, length=32
)
SEVERITY = sa.Enum(
    "critical", "high", "medium", "low", "info", name="policy_severity", native_enum=False, length=32
)
POLICY_RESULT = sa.Enum(
    "pass", "fail", "warning", "error", name="policy_result", native_enum=False, length=32
)
EVIDENCE_STATUS = sa.Enum(
    "pending", "running", "completed", "failed", name="evidence_status", native_enum=False, length=32
)
AUDIT_ACTION = sa.Enum(
    "create",
    "update",
    "delete",
    "classify",
    "policy_check",
    "evidence_generate",
    "login",
    name="audit_action",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])

    op.create_table(
        "jurisdictions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("regulation_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("territories", JSONB, nullable=False),
        sa.Column("risk_taxonomy", JSONB, nullable=False),
        sa.Column("overlay_config", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_jurisdictions"),
        sa.UniqueConstraint("code", name="uq_jurisdictions_code"),
    )
    op.create_index("ix_jurisdictions_code", "jurisdictions", ["code"])
    op.create_index("ix_jurisdictions_is_active", "jurisdictions", ["is_active"])

    op.create_table(
        "ai_systems",
        sa.Column("id", UUID, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("status", SYSTEM_STATUS, nullable=False),
        sa.Column("metadata", JSONB, nullable=False),
        sa.Column("metadata_version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_ai_systems_owner_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_systems"),
        sa.UniqueConstraint("name", name="uq_ai_systems_name"),
    )
    op.create_index("ix_ai_systems_name", "ai_systems", ["name"])
    op.create_index("ix_ai_systems_owner_id", "ai_systems", ["owner_id"])
    op.create_index("ix_ai_systems_status", "ai_systems", ["status"])
    op.create_index("ix_ai_systems_is_deleted", "ai_systems", ["is_deleted"])
    op.create_index("ix_ai_systems_status_deleted", "ai_systems", ["status", "is_deleted"])

    op.create_table(
        "system_metadata",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ai_system_id", UUID, nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("use_case", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("autonomy_level", AUTONOMY, nullable=False),
        sa.Column("data_categories", JSONB, nullable=False),
        sa.Column("deployment_regions", JSONB, nullable=False),
        sa.Column("data_subject_regions", JSONB, nullable=False),
        sa.Column("data_residency", JSONB, nullable=False),
        sa.Column("third_party_models", JSONB, nullable=False),
        sa.Column("affects_minors", sa.Boolean(), nullable=False),
        sa.Column("uses_biometrics", sa.Boolean(), nullable=False),
        sa.Column("uses_generative_ai", sa.Boolean(), nullable=False),
        sa.Column("is_safety_component", sa.Boolean(), nullable=False),
        sa.Column("makes_automated_decisions", sa.Boolean(), nullable=False),
        sa.Column("human_oversight_documented", sa.Boolean(), nullable=False),
        sa.Column("conformity_assessment_done", sa.Boolean(), nullable=False),
        sa.Column("technical_documentation_url", sa.String(length=1024), nullable=True),
        sa.Column("training_data_documented", sa.Boolean(), nullable=False),
        sa.Column("incident_response_plan", sa.Boolean(), nullable=False),
        sa.Column("attributes", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_system_id"],
            ["ai_systems.id"],
            name="fk_system_metadata_ai_system_id_ai_systems",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_metadata"),
        sa.UniqueConstraint("ai_system_id", name="uq_system_metadata_ai_system_id"),
    )
    op.create_index("ix_system_metadata_use_case", "system_metadata", ["use_case"])
    op.create_index("ix_system_metadata_industry", "system_metadata", ["industry"])

    op.create_table(
        "system_metadata_versions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ai_system_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", UUID, nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("diff", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_system_id"],
            ["ai_systems.id"],
            name="fk_system_metadata_versions_ai_system_id_ai_systems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name="fk_system_metadata_versions_changed_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_metadata_versions"),
        sa.UniqueConstraint("ai_system_id", "version", name="uq_system_metadata_versions_version"),
    )
    op.create_index(
        "ix_system_metadata_versions_ai_system_id", "system_metadata_versions", ["ai_system_id"]
    )

    op.create_table(
        "risk_classifications",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ai_system_id", UUID, nullable=False),
        sa.Column("jurisdiction_code", sa.String(length=16), nullable=False),
        sa.Column("risk_tier", RISK_TIER, nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("is_applicable", sa.Boolean(), nullable=False),
        sa.Column("applicability_reasons", JSONB, nullable=False),
        sa.Column("metadata_version", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("evaluated_by_id", UUID, nullable=True),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_system_id"],
            ["ai_systems.id"],
            name="fk_risk_classifications_ai_system_id_ai_systems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["jurisdiction_code"],
            ["jurisdictions.code"],
            name="fk_risk_classifications_jurisdiction_code_jurisdictions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluated_by_id"],
            ["users.id"],
            name="fk_risk_classifications_evaluated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_classifications"),
    )
    op.create_index("ix_risk_classifications_ai_system_id", "risk_classifications", ["ai_system_id"])
    op.create_index(
        "ix_risk_classifications_jurisdiction_code", "risk_classifications", ["jurisdiction_code"]
    )
    op.create_index("ix_risk_classifications_risk_tier", "risk_classifications", ["risk_tier"])
    op.create_index("ix_risk_classifications_evaluated_at", "risk_classifications", ["evaluated_at"])
    op.create_index(
        "ix_risk_class_system_jur_time",
        "risk_classifications",
        ["ai_system_id", "jurisdiction_code", "evaluated_at"],
    )

    op.create_table(
        "policies",
        sa.Column("id", UUID, nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("jurisdiction_code", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("severity", SEVERITY, nullable=False),
        sa.Column("opa_package", sa.String(length=255), nullable=False),
        sa.Column("rego_code", sa.Text(), nullable=True),
        sa.Column("rules", JSONB, nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("applies_to_risk_tiers", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["jurisdiction_code"],
            ["jurisdictions.code"],
            name="fk_policies_jurisdiction_code_jurisdictions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policies"),
        sa.UniqueConstraint("key", "version", name="uq_policies_key_version"),
    )
    op.create_index("ix_policies_key", "policies", ["key"])
    op.create_index("ix_policies_jurisdiction_code", "policies", ["jurisdiction_code"])
    op.create_index("ix_policies_severity", "policies", ["severity"])
    op.create_index("ix_policies_is_active", "policies", ["is_active"])
    op.create_index("ix_policies_is_deleted", "policies", ["is_deleted"])
    op.create_index("ix_policies_jurisdiction_active", "policies", ["jurisdiction_code", "is_active"])

    op.create_table(
        "policy_checks",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ai_system_id", UUID, nullable=False),
        sa.Column("policy_id", UUID, nullable=False),
        sa.Column("policy_key", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("jurisdiction_code", sa.String(length=16), nullable=False),
        sa.Column("severity", SEVERITY, nullable=False),
        sa.Column("result", POLICY_RESULT, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("violations", JSONB, nullable=False),
        sa.Column("remediation", JSONB, nullable=False),
        sa.Column("evaluated_input", JSONB, nullable=False),
        sa.Column("raw_opa_response", JSONB, nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("checked_by_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_system_id"],
            ["ai_systems.id"],
            name="fk_policy_checks_ai_system_id_ai_systems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["policies.id"], name="fk_policy_checks_policy_id_policies", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["checked_by_id"], ["users.id"], name="fk_policy_checks_checked_by_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_checks"),
    )
    op.create_index("ix_policy_checks_ai_system_id", "policy_checks", ["ai_system_id"])
    op.create_index("ix_policy_checks_policy_id", "policy_checks", ["policy_id"])
    op.create_index("ix_policy_checks_policy_key", "policy_checks", ["policy_key"])
    op.create_index("ix_policy_checks_jurisdiction_code", "policy_checks", ["jurisdiction_code"])
    op.create_index("ix_policy_checks_result", "policy_checks", ["result"])
    op.create_index("ix_policy_checks_checked_at", "policy_checks", ["checked_at"])
    op.create_index("ix_policy_checks_system_time", "policy_checks", ["ai_system_id", "checked_at"])
    op.create_index("ix_policy_checks_result_jur", "policy_checks", ["result", "jurisdiction_code"])

    op.create_table(
        "evidence_packages",
        sa.Column("id", UUID, nullable=False),
        sa.Column("ai_system_id", UUID, nullable=False),
        sa.Column("jurisdictions", JSONB, nullable=False),
        sa.Column("status", EVIDENCE_STATUS, nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("pdf_object_key", sa.String(length=1024), nullable=True),
        sa.Column("json_object_key", sa.String(length=1024), nullable=True),
        sa.Column("file_url", sa.String(length=2048), nullable=True),
        sa.Column("json_url", sa.String(length=2048), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary", JSONB, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_by_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_system_id"],
            ["ai_systems.id"],
            name="fk_evidence_packages_ai_system_id_ai_systems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["generated_by_id"],
            ["users.id"],
            name="fk_evidence_packages_generated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_packages"),
    )
    op.create_index("ix_evidence_packages_ai_system_id", "evidence_packages", ["ai_system_id"])
    op.create_index("ix_evidence_packages_status", "evidence_packages", ["status"])
    op.create_index("ix_evidence_packages_task_id", "evidence_packages", ["task_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", UUID, nullable=True),
        sa.Column("action", AUDIT_ACTION, nullable=False),
        sa.Column("actor_id", UUID, nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("changes", JSONB, nullable=False),
        sa.Column("context", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_audit_logs_actor_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id", "created_at"])

    # Audit and assessment tables are append-only: UPDATE and DELETE are blocked in the
    # database itself. Systems are therefore soft-deleted only — a hard DELETE of an
    # ai_systems row would cascade into these tables and be rejected by the trigger.
    for table in ("policy_checks", "risk_classifications", "audit_logs"):
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION reject_mutation_{table}() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '{table} is append-only; % is not permitted', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_mutation_{table}();
            """
        )


def downgrade() -> None:
    for table in ("policy_checks", "risk_classifications", "audit_logs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table};")
        op.execute(f"DROP FUNCTION IF EXISTS reject_mutation_{table}();")
    op.drop_table("audit_logs")
    op.drop_table("evidence_packages")
    op.drop_table("policy_checks")
    op.drop_table("policies")
    op.drop_table("risk_classifications")
    op.drop_table("system_metadata_versions")
    op.drop_table("system_metadata")
    op.drop_table("ai_systems")
    op.drop_table("jurisdictions")
    op.drop_table("users")
