from __future__ import annotations

import json
import base64
import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.operations import (
    DistributedSlidingWindowRateLimiter,
    HashChainAuditLog,
    RateLimiterUnavailable,
    SlidingWindowRateLimiter,
    rate_limiter,
)
from app.store import ReviewStore


client = TestClient(app)


def _jwt(secret: str, claims: dict) -> str:
    def encode(value: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
    header = encode({"alg": "HS256", "typ": "JWT"})
    payload = encode(claims)
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


def test_boundary_adds_security_and_correlation_headers() -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-correlation"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-correlation"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_same_origin_api_prefix_reaches_the_canonical_route() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"


def test_production_fails_closed_without_identity(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AMBROSIA_API_KEYS_JSON", raising=False)
    response = client.get("/packets")
    assert response.status_code == 401


def test_production_allows_cors_preflight_without_identity(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    response = client.options(
        "/reviews",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_staging_origin_header_never_grants_identity(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    response = client.get(
        "/market/SPY/snapshot",
        headers={"Origin": "https://staging.ambrosia.example"},
    )
    assert response.status_code == 401


def test_production_identity_and_route_policy(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setenv(
        "AMBROSIA_API_KEYS_JSON",
        json.dumps({
            "viewer-token-at-least-16": {
                "subject": "viewer-1", "role": "viewer",
                "organization_id": "00000000-0000-0000-0000-000000000002",
            },
            "admin-token-at-least-16x": {
                "subject": "admin-1", "role": "admin",
                "organization_id": "00000000-0000-0000-0000-000000000002",
            },
        }),
    )
    denied = client.post(
        "/roadmap/sync-plans",
        headers={"Authorization": "Bearer viewer-token-at-least-16"},
    )
    assert denied.status_code == 403
    allowed = client.post(
        "/roadmap/sync-plans",
        headers={"Authorization": "Bearer admin-token-at-least-16x"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["strict-transport-security"].startswith("max-age=")


def test_authenticated_role_replaces_spoofable_legacy_header(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setenv("RBAC_ENABLED", "true")
    monkeypatch.setenv(
        "AMBROSIA_API_KEYS_JSON",
        json.dumps({
            "service-token-at-least-16": {
                "subject": "smoke-service", "role": "service", "team": "platform"
            },
        }),
    )
    response = client.get(
        "/providers/status",
        headers={
            "Authorization": "Bearer service-token-at-least-16",
            "X-Ambrosia-Role": "viewer",
        },
    )
    assert response.status_code == 200


def test_readiness_requires_production_identity(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AMBROSIA_API_KEYS_JSON", raising=False)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["identity"]["status"] == "failed"


def test_production_accepts_scoped_hs256_identity(monkeypatch) -> None:
    secret = "a-production-test-secret-that-is-long-enough"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setenv("AMBROSIA_JWT_HS256_SECRET", secret)
    monkeypatch.setenv("AMBROSIA_JWT_ISSUER", "ambrosia")
    monkeypatch.setenv("AMBROSIA_JWT_AUDIENCE", "ambrosia-api")
    token = _jwt(secret, {
        "sub": "analyst-1", "role": "analyst", "iss": "ambrosia",
        "aud": "ambrosia-api", "exp": int(time.time()) + 60,
        "org": "00000000-0000-0000-0000-000000000002",
    })
    response = client.get("/packets", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_production_rejects_expired_jwt(monkeypatch) -> None:
    secret = "a-production-test-secret-that-is-long-enough"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AMBROSIA_JWT_HS256_SECRET", secret)
    token = _jwt(secret, {"sub": "analyst-1", "role": "analyst", "exp": 1})
    response = client.get("/packets", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_body_size_limit(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REQUEST_BYTES", "8")
    response = client.post(
        "/packets",
        content=b"0123456789",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_hash_chain_detects_tampering() -> None:
    audit = HashChainAuditLog()
    audit.append(request_id="r1", principal=None, action="POST", resource="/x", status=401)
    audit.append(request_id="r2", principal=None, action="POST", resource="/y", status=403)
    assert audit.verify() is True
    audit._events[-1].resource = "/tampered"  # intentional adversarial verification
    assert audit.verify() is False


def test_rate_limiter_is_bounded() -> None:
    limiter = SlidingWindowRateLimiter()
    assert limiter.allow("actor", 2)[0] is True
    assert limiter.allow("actor", 2)[0] is True
    assert limiter.allow("actor", 2)[0] is False


def test_distributed_rate_limiter_fails_closed_without_redis_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)
    limiter = DistributedSlidingWindowRateLimiter()
    with pytest.raises(RateLimiterUnavailable):
        limiter.allow("actor", 2)


def test_job_creation_is_idempotent_and_tracks_attempts() -> None:
    local_store = ReviewStore()
    first = local_store.enqueue_job("report", "packet=1", "stable-key")
    second = local_store.enqueue_job("report", "packet=1", "stable-key")
    assert first.id == second.id
    local_store.start_job(first.id)
    running = local_store.get_job(first.id)
    assert running is not None
    assert running.attempt == 1


def test_operational_email_readiness_reports_blockers(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.delenv("AUTH_EMAIL_FROM", raising=False)
    monkeypatch.delenv("AUTH_SES_IDENTITY_ARN", raising=False)
    monkeypatch.delenv("AUTH_SES_CONFIGURATION_SET", raising=False)
    monkeypatch.setenv("AUTH_SES_PRODUCTION_ACCESS_ENABLED", "false")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setenv(
        "AMBROSIA_API_KEYS_JSON",
        json.dumps({
            "ops-token-at-least-16": {
                "subject": "ops-1",
                "role": "admin",
                "organization_id": "00000000-0000-0000-0000-000000000002",
            }
        }),
    )

    response = client.get(
        "/operational/email-readiness",
        headers={"Authorization": "Bearer ops-token-at-least-16"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["environment"] == "staging"
    assert payload["passwordRecoveryAvailable"] is False
    assert payload["checks"]["senderConfigured"] is False
    assert payload["checks"]["sesIdentityArnConfigured"] is False
    assert "AUTH_EMAIL_MODE must be ses" in " ".join(payload["blockers"])


def test_operational_email_readiness_accepts_complete_ses_contract(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("AUTH_EMAIL_MODE", "ses")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.setenv(
        "AUTH_SES_IDENTITY_ARN",
        "arn:aws:ses:ca-central-1:111204669733:identity/example.com",
    )
    monkeypatch.setenv("AUTH_SES_CONFIGURATION_SET", "ambrosia-staging-transactional")
    monkeypatch.setenv("AUTH_SES_PRODUCTION_ACCESS_ENABLED", "true")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setenv(
        "AMBROSIA_API_KEYS_JSON",
        json.dumps({
            "ops-token-at-least-16": {
                "subject": "ops-1",
                "role": "admin",
                "organization_id": "00000000-0000-0000-0000-000000000002",
            }
        }),
    )

    response = client.get(
        "/operational/email-readiness",
        headers={"Authorization": "Bearer ops-token-at-least-16"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["passwordRecoveryAvailable"] is True
    assert payload["checks"] == {
        "senderConfigured": True,
        "sesIdentityArnConfigured": True,
        "configurationSetConfigured": True,
        "productionAccessDeclared": True,
    }
    assert payload["blockers"] == []
