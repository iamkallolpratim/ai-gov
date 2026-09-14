"""Shared pytest fixtures.

Unit tests run against an in-memory SQLite database with the JSONB/UUID columns
mapped to portable types, so they need no Docker services. Integration tests that
require PostgreSQL are marked and skipped unless TEST_DATABASE_URL is set.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# In-memory limits: the test run has no Redis.
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models import (  # noqa: E402
    AISystem,
    AutonomyLevel,
    Jurisdiction,
    Policy,
    PolicySeverity,
    SystemMetadata,
    SystemStatus,
    User,
    UserRole,
)


@pytest.fixture(scope="session")
def sqlite_engine():  # type: ignore[no-untyped-def]
    from sqlalchemy import JSON, String
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _jsonb_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
        return compiler.visit_JSON(JSON(), **kw)

    @compiles(PG_UUID, "sqlite")
    def _uuid_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
        return compiler.visit_VARCHAR(String(36), **kw)

    # StaticPool + check_same_thread keeps the one in-memory database usable from
    # TestClient's worker thread.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(sqlite_engine) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def admin_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@test.example.com",
        full_name="Test Admin",
        role=UserRole.ADMIN,
        hashed_password=hash_password("ChangeMe123!"),
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def viewer_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="viewer@test.example.com",
        full_name="Test Viewer",
        role=UserRole.VIEWER,
        hashed_password=hash_password("ChangeMe123!"),
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def eu_jurisdiction(db: Session) -> Jurisdiction:
    jur = Jurisdiction(
        id=uuid.uuid4(),
        code="EU",
        name="European Union",
        regulation_name="EU AI Act",
        is_active=True,
        territories=["EU", "DE", "FR"],
        overlay_config={"strictness": 100, "extraterritorial": True},
        risk_taxonomy={
            "prohibited_use_cases": ["social_scoring"],
            "high_risk_use_cases": ["employment_screening"],
            "escalate_if": {"is_safety_component": "high"},
            "tier_labels": {"high": "High-risk (Annex III)"},
            "obligations": {"high": ["Art. 14 human oversight"]},
        },
    )
    db.add(jur)
    db.flush()
    return jur


@pytest.fixture
def in_jurisdiction(db: Session) -> Jurisdiction:
    jur = Jurisdiction(
        id=uuid.uuid4(),
        code="IN",
        name="India",
        is_active=True,
        territories=["IN"],
        overlay_config={"strictness": 60},
        risk_taxonomy={"high_risk_use_cases": ["credit_scoring"]},
    )
    db.add(jur)
    db.flush()
    return jur


@pytest.fixture
def high_risk_system(db: Session, admin_user: User) -> AISystem:
    system = AISystem(
        id=uuid.uuid4(),
        name="Resume Screener",
        description="Shortlists applicants",
        owner_id=admin_user.id,
        status=SystemStatus.ACTIVE,
        extra_metadata={},
        metadata_version=1,
        is_deleted=False,
    )
    system.system_metadata = SystemMetadata(
        id=uuid.uuid4(),
        purpose="Shortlist applicants",
        use_case="employment_screening",
        industry="hr_tech",
        autonomy_level=AutonomyLevel.HUMAN_IN_THE_LOOP,
        data_categories=["personal_data"],
        deployment_regions=["EU"],
        data_subject_regions=["EU"],
        data_residency=["EU"],
        third_party_models=[],
        makes_automated_decisions=True,
        human_oversight_documented=False,
        conformity_assessment_done=False,
        training_data_documented=False,
        incident_response_plan=False,
        affects_minors=False,
        uses_biometrics=False,
        uses_generative_ai=False,
        is_safety_component=False,
        attributes={},
    )
    db.add(system)
    db.flush()
    return system


@pytest.fixture
def eu_policy(db: Session, eu_jurisdiction: Jurisdiction) -> Policy:
    policy = Policy(
        id=uuid.uuid4(),
        key="eu_high_risk_obligations",
        name="EU high-risk obligations",
        jurisdiction_code="EU",
        version="1.0.0",
        severity=PolicySeverity.CRITICAL,
        opa_package="aigov.eu.high_risk",
        rego_code=None,
        rules={
            "require_true": ["human_oversight_documented", "conformity_assessment_done"],
            "require_present": ["technical_documentation_url"],
        },
        remediation="Complete Chapter III obligations.",
        applies_to_risk_tiers=["high", "prohibited"],
        is_active=True,
        is_deleted=False,
    )
    db.add(policy)
    db.flush()
    return policy
