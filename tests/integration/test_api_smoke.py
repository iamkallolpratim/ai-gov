"""API-level smoke tests against the SQLite fixture database.

These exercise routing, auth, RBAC and the response envelope without needing Docker.
Every /api/v1 response is wrapped as {"success": true, "data": ...}, so the helper
`data()` unwraps it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import create_app


def data(response):
    """Unwrap the standard success envelope."""
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


def error(response):
    body = response.json()
    assert body["success"] is False, body
    return body["error"]


@pytest.fixture
def client(db, admin_user):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def viewer_client(db, viewer_user):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "test-rid"})
    assert response.headers["X-Request-ID"] == "test-rid"
    # The previous header name still works both ways.
    assert response.headers["X-Correlation-ID"] == "test-rid"


def test_request_id_generated_when_absent(client):
    assert client.get("/health").headers["X-Request-ID"]


def test_security_headers_present(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in headers


def test_ready_endpoint(client):
    body = client.get("/ready").json()
    assert body["status"] in {"ready", "not_ready"}
    assert "database" in body["checks"]


def test_openapi_document_is_valid(client):
    spec = client.get("/openapi.json").json()  # not enveloped: it is the schema itself
    assert "/api/v1/systems" in spec["paths"]
    assert "/api/v1/dashboard/summary" in spec["paths"]
    assert "/api/v1/systems/{system_id}/check-policies" in spec["paths"]


def test_create_and_fetch_system(client):
    payload = {
        "name": "API Test System",
        "description": "Created through the API",
        "system_metadata": {"use_case": "credit_scoring", "deployment_regions": ["EU"]},
    }
    created = client.post("/api/v1/systems", json=payload)
    assert created.status_code == 201, created.text
    system_id = data(created)["id"]

    fetched = client.get(f"/api/v1/systems/{system_id}")
    assert fetched.status_code == 200
    assert data(fetched)["system_metadata"]["use_case"] == "credit_scoring"

    listed = client.get("/api/v1/systems", params={"q": "API Test"})
    assert data(listed)["meta"]["total"] == 1


def test_missing_system_returns_error_envelope(client):
    response = client.get("/api/v1/systems/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
    body = error(response)
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"]


def test_viewer_cannot_mutate(viewer_client):
    response = viewer_client.post("/api/v1/systems", json={"name": "Nope"})
    assert response.status_code == 403
    assert error(response)["code"] == "FORBIDDEN"


def test_unauthenticated_request_rejected(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as anon:
        response = anon.get("/api/v1/systems")
    assert response.status_code == 401
    assert error(response)["code"] == "UNAUTHORIZED"


def test_login_flow(db, admin_user):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as anon:
        token_response = anon.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "ChangeMe123!"},
        )
        assert token_response.status_code == 200
        token = data(token_response)["access_token"]

        me = anon.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert data(me)["email"] == admin_user.email


def test_classify_endpoint(client, high_risk_system, eu_jurisdiction):
    response = client.post(f"/api/v1/systems/{high_risk_system.id}/classify", json={"force": True})
    assert response.status_code == 200, response.text
    body = data(response)
    assert body["most_restrictive_jurisdiction"] == "EU"
    assert body["most_restrictive_tier"] == "high"

    # The endpoint surfaces the full engine output.
    jurisdictions = body["jurisdictions"]
    assert jurisdictions["applicable_jurisdictions"] == ["EU"]
    assert jurisdictions["evaluation_order"] == ["EU"]
    assert jurisdictions["most_restrictive_jurisdictions"] == ["EU"]
    assert jurisdictions["apply_most_restrictive"] is False
    eu = next(m for m in jurisdictions["matches"] if m["code"] == "EU")
    assert "deployment_nexus" in eu["signals"]
    assert any("Deployed in" in r for r in eu["reasons"])


def test_classify_endpoint_orders_multiple_jurisdictions(
    client, high_risk_system, eu_jurisdiction, in_jurisdiction, db
):
    high_risk_system.system_metadata.deployment_regions = ["IN"]
    high_risk_system.system_metadata.offered_in_regions = ["EU"]
    db.flush()

    body = data(client.post(f"/api/v1/systems/{high_risk_system.id}/classify", json={}))[
        "jurisdictions"
    ]
    assert body["evaluation_order"] == ["EU", "IN"]
    assert body["most_restrictive_jurisdictions"] == ["EU"]
    assert body["apply_most_restrictive"] is True
    assert body["conflict_notes"]


def test_detect_endpoint_is_read_only(client, high_risk_system, eu_jurisdiction, db):
    from app.models.risk import RiskClassification

    body = data(client.get(f"/api/v1/jurisdictions/detect/{high_risk_system.id}"))
    assert body["applicable_jurisdictions"] == ["EU"]
    assert body["evaluation_order"] == ["EU"]
    assert db.query(RiskClassification).count() == 0


def test_detect_endpoint_can_hide_inapplicable_regimes(
    client, high_risk_system, eu_jurisdiction, in_jurisdiction
):
    url = f"/api/v1/jurisdictions/detect/{high_risk_system.id}"
    everything = data(client.get(url))
    applicable_only = data(client.get(url, params={"include_inapplicable": False}))

    assert {m["code"] for m in everything["matches"]} == {"EU", "IN"}
    assert {m["code"] for m in applicable_only["matches"]} == {"EU"}
    inapplicable = next(m for m in everything["matches"] if m["code"] == "IN")
    assert inapplicable["applicable"] is False
    assert inapplicable["reasons"]


def test_dashboard_endpoints(client, eu_jurisdiction):
    assert client.get("/api/v1/dashboard/summary", params={"refresh": True}).status_code == 200
    by_jur = client.get("/api/v1/dashboard/by-jurisdiction", params={"refresh": True})
    assert by_jur.status_code == 200
    assert data(by_jur)["jurisdictions"][0]["jurisdiction_code"] == "EU"


def test_jurisdictions_listing(client, eu_jurisdiction):
    codes = [j["code"] for j in data(client.get("/api/v1/jurisdictions"))]
    assert codes == ["EU"]
