from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.artifact_store import ArtifactStore
from app.identity import CSRF_COOKIE, reset_identity_service
from app.main import app
from app.product_analytics import analytics
from app.team_api import reset_team_service
from app.tenant_artifacts import tenant_object_key
from app.tenant_context import reset_organization_id, set_organization_id


@pytest.fixture
def account_client(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    reset_identity_service()
    reset_team_service()
    analytics.reset()
    with TestClient(app) as client:
        signup = client.post(
            "/auth/signup",
            json={
                "email": "analytics@example.com",
                "password": "a long private measurement passphrase",
                "organizationName": "Measured Capital",
                "acceptedTerms": True,
            },
        )
        assert signup.status_code == 201
        verified = client.post(
            "/auth/verify-email",
            json={"token": signup.json()["developmentVerificationToken"]},
        )
        assert verified.status_code == 200
        yield client
    analytics.reset()
    reset_identity_service()
    reset_team_service()


def test_minimized_activation_events_are_idempotent(account_client: TestClient) -> None:
    csrf = account_client.cookies.get(CSRF_COOKIE)
    body = {
        "eventType": "guided_started",
        "surface": "onboarding",
        "objectReference": "packet-private-reference",
        "eventKey": "session-123:guided:onboarding",
        "properties": {"mode": "guided"},
    }
    first = account_client.post("/analytics/events", json=body, headers={"X-CSRF-Token": csrf})
    second = account_client.post("/analytics/events", json=body, headers={"X-CSRF-Token": csrf})
    assert first.status_code == second.status_code == 202
    assert first.json()["inserted"] is True
    assert second.json()["inserted"] is False

    report = account_client.get("/analytics/activation")
    assert report.status_code == 200
    assert report.json()["events"]["guided_started"] == {"count": 1, "uniqueUsers": 1}
    assert "packet-private-reference" not in str(analytics._events)


def test_activation_taxonomy_rejects_arbitrary_properties(account_client: TestClient) -> None:
    csrf = account_client.cookies.get(CSRF_COOKIE)
    response = account_client.post(
        "/analytics/events",
        json={
            "eventType": "guided_started",
            "surface": "onboarding",
            "properties": {"email": "must-not-be-collected@example.com"},
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422


def test_object_keys_require_context_and_cannot_select_another_tenant() -> None:
    with pytest.raises(PermissionError):
        tenant_object_key("exports", "packet-1", "../decision.pdf")

    first = "00000000-0000-0000-0000-000000000002"
    second = "00000000-0000-0000-0000-000000000003"
    token = set_organization_id(first)
    try:
        first_key = tenant_object_key("exports", "packet-1", "../decision.pdf")
    finally:
        reset_organization_id(token)
    token = set_organization_id(second)
    try:
        second_key = tenant_object_key("exports", "packet-1", "../decision.pdf")
    finally:
        reset_organization_id(token)

    assert first_key.startswith(f"tenants/{first}/exports/")
    assert second_key.startswith(f"tenants/{second}/exports/")
    assert first_key != second_key
    assert first_key.endswith("/decision.pdf")
    assert ".." not in first_key


def test_governed_artifact_write_is_tenant_bound_hashed_and_kms_encrypted(monkeypatch) -> None:
    organization_id = "00000000-0000-0000-0000-000000000002"
    statements: list[tuple[str, tuple | None]] = []
    writes: list[dict] = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, parameters=None):
            statements.append((str(statement), parameters))
            return self

    class FakeS3:
        def put_object(self, **request):
            writes.append(request)

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime.invalid/ambrosia")
    monkeypatch.setenv("ARTIFACT_BUCKET", "ambrosia-governed-artifacts")
    monkeypatch.setenv("ARTIFACT_KMS_KEY_ARN", "arn:aws:kms:ca-central-1:123:key/test")
    monkeypatch.setattr("app.artifact_store.psycopg.connect", lambda *_args, **_kwargs: FakeConnection())
    storage = ArtifactStore()
    monkeypatch.setattr(storage, "_client", lambda: FakeS3())

    token = set_organization_id(organization_id)
    try:
        result = storage.persist_json(
            "reports",
            "private-packet-reference",
            "../decision.json",
            {"decision": "needs_more_data", "evidence": ["source-1"]},
        )
    finally:
        reset_organization_id(token)

    assert result["storageStatus"] == "durable"
    assert result["artifactId"]
    assert len(writes) == 1
    request = writes[0]
    assert request["Bucket"] == "ambrosia-governed-artifacts"
    assert request["Key"].startswith(f"tenants/{organization_id}/reports/")
    assert request["Key"].endswith("/decision.json")
    assert "private-packet-reference" not in request["Key"]
    assert request["ServerSideEncryption"] == "aws:kms"
    assert request["SSEKMSKeyId"].endswith("key/test")
    assert json.loads(request["Body"])["decision"] == "needs_more_data"
    assert any("storage_status = %s" in statement and parameters[0] == "durable" for statement, parameters in statements if parameters)
