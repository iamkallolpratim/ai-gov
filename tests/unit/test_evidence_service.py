from __future__ import annotations

import json
import uuid

from app.models.enums import EvidenceStatus
from app.schemas.evidence import EvidenceGenerateRequest
from app.services.evidence import EvidenceGeneratorService
from app.services.pdf import render_evidence_pdf
from app.services.risk import RiskClassificationService
from tests.unit.test_policy_service import FakeOPA


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def ensure_bucket(self) -> None:  # pragma: no cover
        pass

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self.objects[key] = data
        return key

    def presigned_url(self, key: str, expires: int | None = None) -> str:
        return f"https://storage.test/{key}"

    def healthy(self) -> bool:  # pragma: no cover
        return True


def test_request_package_defaults_to_applicable_jurisdictions(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    RiskClassificationService(db).classify(high_risk_system, actor=admin_user)
    package = EvidenceGeneratorService(db).request_package(
        high_risk_system.id, EvidenceGenerateRequest(), actor=admin_user
    )
    assert package.status == EvidenceStatus.PENDING
    assert package.jurisdictions == ["EU"]


def test_build_produces_pdf_and_json(db, high_risk_system, eu_jurisdiction, eu_policy, admin_user):
    from app.services.policy import PolicyService

    PolicyService(
        db, opa=FakeOPA({"allow": False, "violations": [{"msg": "no oversight"}]})
    ).evaluate_system(high_risk_system, actor=admin_user)

    storage = FakeStorage()
    service = EvidenceGeneratorService(db, storage=storage)  # type: ignore[arg-type]
    package = service.request_package(
        high_risk_system.id,
        EvidenceGenerateRequest(include_history=True, notes="Q3 audit"),
        actor=admin_user,
    )
    built = service.build(package.id)

    assert built.status == EvidenceStatus.COMPLETED
    assert built.checksum_sha256 and len(built.checksum_sha256) == 64
    assert built.file_url.endswith("evidence.pdf")

    pdf = storage.objects[built.pdf_object_key]
    assert pdf.startswith(b"%PDF")

    document = json.loads(storage.objects[built.json_object_key])
    assert document["system"]["name"] == "Resume Screener"
    assert document["classifications"][0]["jurisdiction_code"] == "EU"
    assert document["summary"]["failed"] == 1
    assert document["notes"] == "Q3 audit"


def test_pdf_renders_without_checks():
    document = {
        "package_id": str(uuid.uuid4()),
        "generated_at": "2026-01-01T00:00:00",
        "generated_by": "admin@test.example.com",
        "jurisdictions": ["EU"],
        "system": {
            "id": str(uuid.uuid4()),
            "name": "Empty System",
            "description": None,
            "status": "draft",
            "owner": "admin@test.example.com",
            "metadata_version": 1,
        },
        "metadata": {},
        "classifications": [],
        "policy_checks": [],
        "history": [],
        "summary": {},
    }
    assert render_evidence_pdf(document).startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Recovery: stale expiry and retry
# ---------------------------------------------------------------------------

from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.exceptions import ConflictError, NotFoundError  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402

OLD = timedelta(seconds=settings.EVIDENCE_STALE_AFTER_SECONDS + 3600)


def _package(db, system, actor, *, status, age=timedelta(0), options=None):
    service = EvidenceGeneratorService(db)
    package = service.request_package(
        system.id, EvidenceGenerateRequest(**(options or {})), actor=actor
    )
    package.status = status
    stamp = datetime.now(UTC) - age
    package.created_at = stamp
    package.updated_at = stamp
    db.flush()
    return package


def test_expire_stale_fails_old_in_flight_packages(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    old_pending = _package(db, high_risk_system, admin_user, status=EvidenceStatus.PENDING, age=OLD)
    old_running = _package(db, high_risk_system, admin_user, status=EvidenceStatus.RUNNING, age=OLD)

    assert EvidenceGeneratorService(db).expire_stale() == 2

    for package in (old_pending, old_running):
        assert package.status == EvidenceStatus.FAILED
        assert "did not complete" in package.error_message
        assert "Retry" in package.error_message


def test_expire_stale_leaves_fresh_and_settled_packages_alone(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    fresh = _package(db, high_risk_system, admin_user, status=EvidenceStatus.PENDING)
    done = _package(db, high_risk_system, admin_user, status=EvidenceStatus.COMPLETED, age=OLD)
    failed = _package(db, high_risk_system, admin_user, status=EvidenceStatus.FAILED, age=OLD)
    failed.error_message = "original error"
    db.flush()

    assert EvidenceGeneratorService(db).expire_stale() == 0
    assert fresh.status == EvidenceStatus.PENDING
    assert done.status == EvidenceStatus.COMPLETED
    assert failed.error_message == "original error"


def test_expire_stale_is_idempotent_and_audited(db, high_risk_system, eu_jurisdiction, admin_user):
    package = _package(db, high_risk_system, admin_user, status=EvidenceStatus.PENDING, age=OLD)
    service = EvidenceGeneratorService(db)

    assert service.expire_stale() == 1
    assert service.expire_stale() == 0

    entries = [
        e
        for e in db.execute(select(AuditLog).where(AuditLog.resource_id == package.id))
        .scalars()
        .all()
        if e.new_values.get("reason") == "stale"
    ]
    assert len(entries) == 1
    assert entries[0].actor_type == "system"


def test_retry_resets_a_failed_package_and_keeps_its_options(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    package = _package(
        db,
        high_risk_system,
        admin_user,
        status=EvidenceStatus.FAILED,
        options={"include_history": True, "notes": "Q3 audit"},
    )
    package.error_message = "Could not queue the generation job"
    package.task_id = "old-task"
    db.flush()

    retried = EvidenceGeneratorService(db).retry(high_risk_system.id, package.id, actor=admin_user)

    assert retried.id == package.id  # the same record, not a duplicate
    assert retried.status == EvidenceStatus.PENDING
    assert retried.error_message is None
    assert retried.task_id is None
    assert retried.summary["options"]["include_history"] is True
    assert retried.summary["options"]["notes"] == "Q3 audit"


def test_retry_recovers_a_stalled_package(db, high_risk_system, eu_jurisdiction, admin_user):
    package = _package(db, high_risk_system, admin_user, status=EvidenceStatus.PENDING, age=OLD)
    retried = EvidenceGeneratorService(db).retry(high_risk_system.id, package.id, actor=admin_user)
    assert retried.status == EvidenceStatus.PENDING


@pytest.mark.parametrize(
    "status,age,message",
    [
        (EvidenceStatus.COMPLETED, timedelta(0), "already completed"),
        (EvidenceStatus.PENDING, timedelta(0), "still being generated"),
        (EvidenceStatus.RUNNING, timedelta(0), "still being generated"),
    ],
)
def test_retry_refuses_completed_and_genuinely_in_flight(
    db, high_risk_system, eu_jurisdiction, admin_user, status, age, message
):
    package = _package(db, high_risk_system, admin_user, status=status, age=age)
    with pytest.raises(ConflictError, match=message):
        EvidenceGeneratorService(db).retry(high_risk_system.id, package.id, actor=admin_user)


def test_retry_rejects_a_package_from_another_system(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    import uuid as _uuid

    package = _package(db, high_risk_system, admin_user, status=EvidenceStatus.FAILED)
    with pytest.raises(NotFoundError):
        EvidenceGeneratorService(db).retry(_uuid.uuid4(), package.id, actor=admin_user)


def test_retried_old_package_is_in_flight_not_stale(
    db, high_risk_system, eu_jurisdiction, admin_user
):
    """Staleness runs from the last activity, not from when the package was first requested.

    Regression: judging by `created_at`, a package first requested weeks ago looked
    stalled the instant it was retried — the UI stopped polling it, offered Retry again,
    and the expiry task would have failed it while the worker was still generating it.
    """
    from app.services.evidence import _as_utc

    package = _package(db, high_risk_system, admin_user, status=EvidenceStatus.FAILED, age=OLD)
    service = EvidenceGeneratorService(db)

    service.retry(high_risk_system.id, package.id, actor=admin_user)

    assert package.status == EvidenceStatus.PENDING
    assert _as_utc(package.created_at) < service.stale_cutoff()  # still requested long ago
    assert service.is_stale(package) is False
    assert service.expire_stale() == 0
    with pytest.raises(ConflictError, match="still being generated"):
        service.retry(high_risk_system.id, package.id, actor=admin_user)
