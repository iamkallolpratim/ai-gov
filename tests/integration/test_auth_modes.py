"""Authentication in both modes, plus the audit trail that must work in each.

`AUTH_DISABLED` is read from settings at request time, so these tests flip the flag with
monkeypatch and build a fresh app per case.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.principal import SYSTEM_USER_EMAIL
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.audit import AuditLog
from app.models.enums import ActorType, UserRole


def data(response):
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


def error(response):
    body = response.json()
    assert body["success"] is False, body
    return body["error"]


@pytest.fixture
def client_factory(db):
    """Builds a TestClient bound to the test session, for the current auth mode."""

    def _make() -> TestClient:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)

    return _make


@pytest.fixture
def auth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", False)


@pytest.fixture
def auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)


def token_for(user) -> dict[str, str]:
    token = create_access_token(str(user.id), role=str(user.role), email=user.email)
    return {"Authorization": f"Bearer {token}"}


SYSTEM_PAYLOAD = {
    "name": "Mode Test System",
    "system_metadata": {"use_case": "credit_scoring", "deployment_regions": ["EU"]},
}


# ---------------------------------------------------------------------------
# Authentication enforced
# ---------------------------------------------------------------------------


class TestAuthEnabled:
    def test_protected_endpoint_rejects_anonymous(self, client_factory, auth_enabled):
        response = client_factory().get("/api/v1/systems")
        assert response.status_code == 401
        assert error(response)["code"] == "UNAUTHORIZED"

    def test_valid_token_is_accepted(self, client_factory, auth_enabled, admin_user):
        response = client_factory().get("/api/v1/systems", headers=token_for(admin_user))
        assert response.status_code == 200

    def test_invalid_token_rejected(self, client_factory, auth_enabled):
        response = client_factory().get(
            "/api/v1/systems", headers={"Authorization": "Bearer not-a-token"}
        )
        assert response.status_code == 401

    def test_login_returns_access_and_refresh(self, client_factory, auth_enabled, admin_user):
        client = client_factory()
        body = data(
            client.post(
                "/api/v1/auth/login",
                json={"email": admin_user.email, "password": "ChangeMe123!"},
            )
        )
        assert body["access_token"] and body["refresh_token"]
        assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        refreshed = data(
            client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
        )
        assert refreshed["access_token"]

    def test_refresh_token_rejected_as_access_token(self, client_factory, auth_enabled, admin_user):
        client = client_factory()
        body = data(
            client.post(
                "/api/v1/auth/login",
                json={"email": admin_user.email, "password": "ChangeMe123!"},
            )
        )
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['refresh_token']}"}
        )
        assert response.status_code == 401

    def test_bad_password_is_rejected(self, client_factory, auth_enabled, admin_user):
        response = client_factory().post(
            "/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_me_returns_the_real_user(self, client_factory, auth_enabled, admin_user):
        body = data(client_factory().get("/api/v1/auth/me", headers=token_for(admin_user)))
        assert body["email"] == admin_user.email
        assert body["is_system"] is False

    def test_viewer_cannot_write(self, client_factory, auth_enabled, viewer_user):
        response = client_factory().post(
            "/api/v1/systems", json=SYSTEM_PAYLOAD, headers=token_for(viewer_user)
        )
        assert response.status_code == 403
        assert error(response)["code"] == "FORBIDDEN"

    def test_viewer_can_read(self, client_factory, auth_enabled, viewer_user):
        assert (
            client_factory().get("/api/v1/systems", headers=token_for(viewer_user)).status_code
            == 200
        )

    def test_risk_officer_can_write_but_not_manage_policies(
        self, client_factory, auth_enabled, db, admin_user
    ):
        from app.core.security import hash_password
        from app.models.user import User

        officer = User(
            email="officer@test.example.com",
            full_name="Officer",
            role=UserRole.RISK_OFFICER,
            hashed_password=hash_password("ChangeMe123!"),
            is_active=True,
            is_deleted=False,
        )
        db.add(officer)
        db.flush()
        client = client_factory()

        assert (
            client.post("/api/v1/systems", json=SYSTEM_PAYLOAD, headers=token_for(officer))
        ).status_code == 201
        # Policy management is admin-only.
        assert client.get("/api/v1/audit-logs", headers=token_for(officer)).status_code == 403

    def test_audit_logs_are_admin_only(self, client_factory, auth_enabled, admin_user, viewer_user):
        client = client_factory()
        assert client.get("/api/v1/audit-logs", headers=token_for(admin_user)).status_code == 200
        assert client.get("/api/v1/audit-logs", headers=token_for(viewer_user)).status_code == 403

    def test_system_principal_cannot_log_in(self, client_factory, auth_enabled, db):
        from app.core.principal import get_system_user

        get_system_user(db)
        response = client_factory().post(
            "/api/v1/auth/login",
            json={"email": SYSTEM_USER_EMAIL, "password": "ChangeMe123!"},
        )
        assert response.status_code == 401

    def test_documented_seed_credentials_actually_work(self, client_factory, auth_enabled, db):
        """The literal README quick-start request, against the real seeded accounts.

        This is the end-to-end guard for the `@aigov.local` class of bug: the seeder
        writes through the ORM, which does not validate emails, so only an actual login
        proves the shipped credentials are usable.
        """
        from app.db.seed import DEMO_PASSWORD, USERS, seed_users

        seed_users(db)
        client = client_factory()

        for account in USERS:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": account["email"], "password": DEMO_PASSWORD},
            )
            assert response.status_code == 200, (
                f"seeded account {account['email']} cannot log in: {response.text}"
            )
            token = data(response)["access_token"]

            me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200, f"/auth/me fails for {account['email']}: {me.text}"
            assert data(me)["email"] == account["email"]
            assert data(me)["role"] == account["role"]

    def test_mode_endpoint_reports_enabled(self, client_factory, auth_enabled):
        body = data(client_factory().get("/api/v1/auth/mode"))
        assert body["auth_enabled"] is True
        assert body["auth_disabled"] is False


# ---------------------------------------------------------------------------
# Authentication disabled
# ---------------------------------------------------------------------------


class TestAuthDisabled:
    def test_protected_endpoints_work_without_a_token(self, client_factory, auth_disabled):
        assert client_factory().get("/api/v1/systems").status_code == 200

    def test_writes_work_without_a_token(self, client_factory, auth_disabled):
        response = client_factory().post("/api/v1/systems", json=SYSTEM_PAYLOAD)
        assert response.status_code == 201, response.text

    def test_me_returns_the_system_principal(self, client_factory, auth_disabled):
        body = data(client_factory().get("/api/v1/auth/me"))
        assert body["email"] == SYSTEM_USER_EMAIL
        assert body["role"] == UserRole.ADMIN
        assert body["is_system"] is True

    def test_admin_only_endpoints_are_reachable(self, client_factory, auth_disabled):
        assert client_factory().get("/api/v1/audit-logs").status_code == 200

    def test_garbage_token_is_ignored_rather_than_rejected(self, client_factory, auth_disabled):
        response = client_factory().get(
            "/api/v1/systems", headers={"Authorization": "Bearer nonsense"}
        )
        assert response.status_code == 200

    def test_mode_endpoint_reports_disabled(self, client_factory, auth_disabled):
        body = data(client_factory().get("/api/v1/auth/mode"))
        assert body["auth_disabled"] is True

    def test_health_reports_the_mode(self, client_factory, auth_disabled):
        assert client_factory().get("/health").json()["auth_enabled"] is False

    def test_only_one_system_principal_is_ever_created(self, client_factory, auth_disabled, db):
        from sqlalchemy import func, select

        from app.models.user import User

        client = client_factory()
        for _ in range(3):
            client.get("/api/v1/auth/me")
        count = db.execute(
            select(func.count()).select_from(User).where(User.email == SYSTEM_USER_EMAIL)
        ).scalar_one()
        assert count == 1


# ---------------------------------------------------------------------------
# Audit trail — must work in both modes
# ---------------------------------------------------------------------------


class TestAuditTrailBothModes:
    def _latest(self, db) -> AuditLog:
        from sqlalchemy import select

        return list(
            db.execute(select(AuditLog).order_by(AuditLog.created_at.desc())).scalars().all()
        )[0]

    def test_authenticated_write_is_attributed_to_the_user(
        self, client_factory, auth_enabled, db, admin_user
    ):
        client_factory().post("/api/v1/systems", json=SYSTEM_PAYLOAD, headers=token_for(admin_user))
        entry = self._latest(db)
        assert entry.resource_type == "ai_system"
        assert entry.actor_type == ActorType.USER
        assert entry.actor_id == admin_user.id
        assert entry.actor_label == str(admin_user.id)
        assert entry.request_id

    def test_unauthenticated_write_is_attributed_to_system(self, client_factory, auth_disabled, db):
        client_factory().post("/api/v1/systems", json=SYSTEM_PAYLOAD)
        entry = self._latest(db)
        assert entry.actor_type == ActorType.SYSTEM
        assert entry.actor_label == "system"
        assert entry.actor_email == SYSTEM_USER_EMAIL

    def test_client_fingerprint_is_captured(self, client_factory, auth_disabled, db):
        client_factory().post(
            "/api/v1/systems",
            json=SYSTEM_PAYLOAD,
            headers={"User-Agent": "pytest-agent/1.0", "X-Forwarded-For": "203.0.113.10"},
        )
        entry = self._latest(db)
        assert entry.ip_address == "203.0.113.10"
        assert entry.user_agent == "pytest-agent/1.0"

    def test_update_records_before_and_after(self, client_factory, auth_disabled, db):
        client = client_factory()
        system_id = data(client.post("/api/v1/systems", json=SYSTEM_PAYLOAD))["id"]
        client.patch(f"/api/v1/systems/{system_id}", json={"description": "changed"})

        entry = self._latest(db)
        assert entry.old_values.get("description") is None
        assert entry.new_values.get("description") == "changed"

    def test_audit_endpoint_filters_by_actor_type(self, client_factory, auth_disabled, db):
        client = client_factory()
        client.post("/api/v1/systems", json=SYSTEM_PAYLOAD)
        body = data(client.get("/api/v1/audit-logs", params={"actor_type": "system"}))
        assert body["meta"]["total"] >= 1
        assert all(item["actor_type"] == "system" for item in body["items"])

    def test_audit_entries_are_immutable_through_the_api(self, client_factory, auth_disabled):
        client = client_factory()
        client.post("/api/v1/systems", json=SYSTEM_PAYLOAD)
        log_id = data(client.get("/api/v1/audit-logs"))["items"][0]["id"]
        # No write route exists for the audit trail at all.
        assert client.delete(f"/api/v1/audit-logs/{log_id}").status_code == 405
        assert client.patch(f"/api/v1/audit-logs/{log_id}", json={}).status_code == 405


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    @pytest.fixture
    def limited(self, monkeypatch):
        """Enable the limiter for one test, with a tiny in-memory budget."""
        from app.api.rate_limit import limiter

        monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/minute")
        monkeypatch.setattr(limiter, "enabled", True)
        limiter.reset()
        yield
        limiter.reset()

    def test_login_is_rate_limited(self, client_factory, auth_enabled, limited, admin_user):
        client = client_factory()
        payload = {"email": admin_user.email, "password": "wrong-password"}
        statuses = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(5)]

        assert statuses[:3] == [401, 401, 401]
        assert statuses[-1] == 429

        body = error(client.post("/api/v1/auth/login", json=payload))
        assert body["code"] == "RATE_LIMITED"

    def test_successful_request_under_a_limit_returns_headers_not_a_500(
        self, client_factory, auth_enabled, limited, admin_user
    ):
        """slowapi injects rate-limit headers into a `response` parameter.

        Without that parameter the decorator raises *after* the endpoint returns, so
        only a **successful** rate-limited call reveals it — failing logins never get
        far enough.
        """
        response = client_factory().post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "ChangeMe123!"},
        )
        assert response.status_code == 200, response.text
        assert data(response)["access_token"]
        assert "x-ratelimit-limit" in {k.lower() for k in response.headers}

    def test_limit_uses_the_configured_value_at_request_time(
        self, client_factory, auth_enabled, limited, monkeypatch, admin_user
    ):
        monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
        client = client_factory()
        payload = {"email": admin_user.email, "password": "wrong-password"}
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
        assert client.post("/api/v1/auth/login", json=payload).status_code == 429


# ---------------------------------------------------------------------------
# Background queue failures
# ---------------------------------------------------------------------------


class TestEvidenceDispatchFailure:
    """Redis being down must not surface as an opaque 500.

    Evidence generation is queued through Celery. If the broker is unreachable the
    dispatch raises inside the endpoint, which previously produced a raw traceback and
    left the package row stuck on "pending" forever.
    """

    def test_broker_failure_returns_503_and_marks_the_package_failed(
        self, client_factory, auth_disabled, db, monkeypatch, high_risk_system, eu_jurisdiction
    ):
        from kombu.exceptions import OperationalError

        import app.workers.tasks as tasks
        from app.models.evidence import EvidencePackage

        def explode(*_args, **_kwargs):
            raise OperationalError("[Errno 111] Connection refused")

        monkeypatch.setattr(tasks.generate_evidence_package, "delay", explode)

        response = client_factory().post(f"/api/v1/systems/{high_risk_system.id}/evidence", json={})

        assert response.status_code == 503
        body = error(response)
        assert body["code"] == "TASK_QUEUE_UNAVAILABLE"
        assert "worker" in body["message"].lower()

        # The package must not be left pending, which would poll forever in the UI.
        from sqlalchemy import select

        package = (
            db.execute(select(EvidencePackage).order_by(EvidencePackage.created_at.desc()))
            .scalars()
            .first()
        )
        assert package is not None
        assert package.status == "failed"
        assert "Connection refused" in (package.error_message or "")


class TestEvidenceRetry:
    """`POST /systems/{id}/evidence/{package_id}/retry` re-queues the same package."""

    @pytest.fixture
    def dispatched(self, monkeypatch):
        """Records dispatches instead of publishing to a broker."""
        import app.workers.tasks as tasks

        calls: list[str] = []

        class FakeResult:
            id = "fake-task-id"

        def fake_delay(package_id, *_args, **_kwargs):
            calls.append(package_id)
            return FakeResult()

        monkeypatch.setattr(tasks.generate_evidence_package, "delay", fake_delay)
        return calls

    def _failed_package(self, db, system, actor, status="FAILED"):
        from app.models.enums import EvidenceStatus
        from app.schemas.evidence import EvidenceGenerateRequest
        from app.services.evidence import EvidenceGeneratorService

        package = EvidenceGeneratorService(db).request_package(
            system.id, EvidenceGenerateRequest(), actor=actor
        )
        package.status = EvidenceStatus[status]
        package.error_message = "Could not queue the generation job: [Errno 111] Connection refused"
        db.flush()
        return package

    def test_retry_requeues_the_same_package(
        self,
        client_factory,
        auth_disabled,
        db,
        dispatched,
        high_risk_system,
        eu_jurisdiction,
        admin_user,
    ):
        package = self._failed_package(db, high_risk_system, admin_user)

        response = client_factory().post(
            f"/api/v1/systems/{high_risk_system.id}/evidence/{package.id}/retry"
        )

        assert response.status_code == 202, response.text
        body = data(response)
        assert body["package_id"] == str(package.id)
        assert body["task_id"] == "fake-task-id"
        assert dispatched == [str(package.id)]
        db.refresh(package)
        assert package.status == "pending"
        assert package.error_message is None

    def test_retry_of_a_completed_package_conflicts(
        self,
        client_factory,
        auth_disabled,
        db,
        dispatched,
        high_risk_system,
        eu_jurisdiction,
        admin_user,
    ):
        package = self._failed_package(db, high_risk_system, admin_user, status="COMPLETED")
        response = client_factory().post(
            f"/api/v1/systems/{high_risk_system.id}/evidence/{package.id}/retry"
        )
        assert response.status_code == 409
        assert error(response)["code"] == "CONFLICT"
        assert dispatched == []

    def test_retry_for_the_wrong_system_is_not_found(
        self,
        client_factory,
        auth_disabled,
        db,
        dispatched,
        high_risk_system,
        eu_jurisdiction,
        admin_user,
    ):
        import uuid as _uuid

        package = self._failed_package(db, high_risk_system, admin_user)
        response = client_factory().post(
            f"/api/v1/systems/{_uuid.uuid4()}/evidence/{package.id}/retry"
        )
        assert response.status_code == 404
        assert dispatched == []

    def test_viewer_cannot_retry(
        self,
        client_factory,
        auth_enabled,
        db,
        dispatched,
        high_risk_system,
        eu_jurisdiction,
        admin_user,
        viewer_user,
    ):
        package = self._failed_package(db, high_risk_system, admin_user)
        response = client_factory().post(
            f"/api/v1/systems/{high_risk_system.id}/evidence/{package.id}/retry",
            headers=token_for(viewer_user),
        )
        assert response.status_code == 403
        assert dispatched == []

    def test_broker_failure_on_retry_returns_503_and_stays_failed(
        self,
        client_factory,
        auth_disabled,
        db,
        monkeypatch,
        high_risk_system,
        eu_jurisdiction,
        admin_user,
    ):
        from kombu.exceptions import OperationalError

        import app.workers.tasks as tasks

        def explode(*_args, **_kwargs):
            raise OperationalError("[Errno 111] Connection refused")

        monkeypatch.setattr(tasks.generate_evidence_package, "delay", explode)
        package = self._failed_package(db, high_risk_system, admin_user)

        response = client_factory().post(
            f"/api/v1/systems/{high_risk_system.id}/evidence/{package.id}/retry"
        )

        assert response.status_code == 503
        assert error(response)["code"] == "TASK_QUEUE_UNAVAILABLE"
        db.refresh(package)
        assert package.status == "failed"
