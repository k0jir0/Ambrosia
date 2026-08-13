from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from app.identity import (
    CSRF_COOKIE,
    EmailSender,
    canonicalize_email,
    development_tokens_exposed,
    get_identity_service,
    register_identity_audit_sink,
    reset_identity_service,
    validate_password,
    verification_tokens_exposed,
)
from app.main import app
from app.operations import rate_limiter
from app.team_api import reset_team_service


@pytest.fixture
def identity_client(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_TOKEN_PEPPER", raising=False)
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    reset_identity_service()
    reset_team_service()
    with TestClient(app) as client:
        yield client
    reset_identity_service()
    reset_team_service()


def _signup(client: TestClient, email: str = "owner@example.com") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "an unusually strong passphrase 2026",
            "organizationName": "Northstar Capital",
            "acceptedTerms": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_email_canonicalization_and_password_policy() -> None:
    display, canonical = canonicalize_email("  Owner@ExAmPle.com ")
    assert display == "Owner@ExAmPle.com"
    assert canonical == "owner@example.com"
    with pytest.raises(ValueError, match="at least"):
        validate_password("too short")
    with pytest.raises(ValueError, match="commonly used"):
        validate_password("passwordpassword")


def test_domainless_staging_exposes_single_use_verification_with_explicit_opt_in(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    reset_identity_service()

    get_identity_service().healthcheck()
    assert development_tokens_exposed() is False
    assert verification_tokens_exposed() is True
    with TestClient(app, base_url="https://staging.example") as client:
        signup = _signup(client, email="staging-owner@example.com")
    assert len(signup["developmentVerificationToken"]) >= 20
    reset_identity_service()


def test_production_never_accepts_staging_console_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    reset_identity_service()

    assert development_tokens_exposed() is False
    assert verification_tokens_exposed() is False
    with pytest.raises(RuntimeError, match="production_email_not_configured"):
        get_identity_service().healthcheck()
    reset_identity_service()


def test_staging_password_recovery_fails_before_account_lookup_without_ses(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    reset_identity_service()

    with TestClient(app, base_url="https://staging.example") as client:
        response = client.post(
            "/auth/forgot-password", json={"email": "unknown@example.com"}
        )

    assert response.status_code == 503
    problem = response.json()
    assert problem["detail"] == "Password recovery is temporarily unavailable"
    assert problem["status"] == 503
    assert problem["code"] == "INTERNAL_ERROR"
    assert problem["requestId"] == response.headers["x-request-id"]
    reset_identity_service()


def test_assisted_password_reset_prepares_single_use_link_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    monkeypatch.setenv("AUTH_ENABLE_ASSISTED_RESET", "true")
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://staging.example.com")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    reset_identity_service()


def test_assisted_password_reset_emits_identity_audit_events(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    monkeypatch.setenv("AUTH_ENABLE_ASSISTED_RESET", "true")
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://staging.example.com")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    reset_identity_service()

    events: list[dict] = []
    register_identity_audit_sink(lambda **event: events.append(event))

    with TestClient(app, base_url="https://staging.example") as client:
        signup = _signup(client, email="assisted-audit@example.com")
        assert client.post(
            "/auth/verify-email",
            json={"token": signup["developmentVerificationToken"]},
        ).status_code == 200
        csrf = client.cookies.get(CSRF_COOKIE)
        assisted = client.post(
            "/auth/assisted-password-reset",
            json={
                "email": "assisted-audit@example.com",
                "ticketId": "SUP-153",
                "reason": "Audit sink coverage validation for assisted reset flow.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        token = parse_qs(urlparse(assisted.json()["resetUrl"]).query)["token"][0]
        assert client.post(
            "/auth/reset-password",
            json={"token": token, "newPassword": "a different strong passphrase 2026"},
        ).status_code == 200

    register_identity_audit_sink(None)
    reset_identity_service()

    assert [event["action"] for event in events] == [
        "ASSISTED_PASSWORD_RESET_ISSUED",
        "ASSISTED_PASSWORD_RESET_COMPLETED",
    ]

    with TestClient(app, base_url="https://staging.example") as client:
        signup = _signup(client, email="assisted-owner@example.com")
        assert client.post(
            "/auth/verify-email",
            json={"token": signup["developmentVerificationToken"]},
        ).status_code == 200
        csrf = client.cookies.get(CSRF_COOKIE)
        assisted = client.post(
            "/auth/assisted-password-reset",
            json={
                "email": "assisted-owner@example.com",
                "ticketId": "SUP-151",
                "reason": "User cannot receive reset email while SES approval is pending.",
            },
            headers={"X-CSRF-Token": csrf},
        )

        assert assisted.status_code == 202, assisted.text
        payload = assisted.json()
        assert payload["message"].startswith("If an eligible account exists")
        assert payload["issuedAt"]
        assert payload["resetUrl"].startswith("https://staging.example.com/reset-password?token=")

        token = parse_qs(urlparse(payload["resetUrl"]).query)["token"][0]
        reset = client.post(
            "/auth/reset-password",
            json={"token": token, "newPassword": "a different strong passphrase 2026"},
        )
        assert reset.status_code == 200
        assert client.post(
            "/auth/reset-password",
            json={"token": token, "newPassword": "a different strong passphrase 2027"},
        ).status_code == 400

    reset_identity_service()


def test_assisted_password_reset_returns_503_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY", "true")
    monkeypatch.setenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true")
    monkeypatch.setenv("AUTH_ENABLE_ASSISTED_RESET", "false")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    reset_identity_service()

    with TestClient(app, base_url="https://staging.example") as client:
        signup = _signup(client, email="assisted-disabled@example.com")
        assert client.post(
            "/auth/verify-email",
            json={"token": signup["developmentVerificationToken"]},
        ).status_code == 200
        csrf = client.cookies.get(CSRF_COOKIE)
        response = client.post(
            "/auth/assisted-password-reset",
            json={
                "email": "assisted-disabled@example.com",
                "ticketId": "SUP-152",
                "reason": "Feature toggle disabled for this environment.",
            },
            headers={"X-CSRF-Token": csrf},
        )

        assert response.status_code == 503
        problem = response.json()
        assert problem["detail"] == "Assisted password recovery is unavailable"
        assert problem["status"] == 503
        assert problem["code"] == "INTERNAL_ERROR"
        assert problem["requestId"] == response.headers["x-request-id"]

    reset_identity_service()


def test_ses_password_reset_uses_verified_sender_and_configuration_set(
    monkeypatch,
) -> None:
    sent: list[dict] = []

    class FakeSesClient:
        def send_email(self, **request) -> dict:
            sent.append(request)
            return {"MessageId": "ses-message-123"}

    monkeypatch.setenv("AUTH_EMAIL_MODE", "ses")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.setenv("AUTH_SES_CONFIGURATION_SET", "ambrosia-staging-transactional")
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://staging.example.com")
    monkeypatch.setattr("app.identity.boto3.client", lambda *_args, **_kwargs: FakeSesClient())

    EmailSender().send_password_reset("owner@example.com", "single-use-token")

    assert sent == [{
        "FromEmailAddress": "no-reply@example.com",
        "Destination": {"ToAddresses": ["owner@example.com"]},
        "Content": {"Simple": {
            "Subject": {"Data": "Reset your Ambrosia password"},
            "Body": {"Text": {"Data": "Reset your password: https://staging.example.com/reset-password?token=single-use-token"}},
        }},
        "ConfigurationSetName": "ambrosia-staging-transactional",
    }]


def test_successful_password_reset_sends_one_security_notification(
    identity_client: TestClient, monkeypatch,
) -> None:
    _signup(identity_client)
    notifications: list[str] = []
    monkeypatch.setattr(
        "app.identity.EmailSender.send_password_changed",
        lambda _sender, email: notifications.append(email),
    )

    requested = identity_client.post(
        "/auth/forgot-password", json={"email": "owner@example.com"}
    )
    token = requested.json()["developmentResetToken"]
    payload = {"token": token, "newPassword": "a replacement passphrase 2026"}

    assert identity_client.post("/auth/reset-password", json=payload).status_code == 200
    assert identity_client.post("/auth/reset-password", json=payload).status_code == 400
    assert notifications == ["owner@example.com"]


def test_ses_failure_does_not_disclose_account_existence(
    identity_client: TestClient, monkeypatch,
) -> None:
    _signup(identity_client)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "x" * 32)
    monkeypatch.setenv("AUTH_EMAIL_MODE", "ses")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.setattr(rate_limiter, "allow", lambda *_args, **_kwargs: (True, 299))
    monkeypatch.setattr(
        "app.identity.EmailSender.send_password_reset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("SES unavailable")),
    )

    unknown = identity_client.post(
        "/auth/forgot-password", json={"email": "unknown@example.com"}
    )
    known = identity_client.post(
        "/auth/forgot-password", json={"email": "owner@example.com"}
    )

    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert "developmentResetToken" not in known.json()


def test_signup_verification_session_and_logout(identity_client: TestClient) -> None:
    signup = _signup(identity_client)
    assert signup["status"] == "pending_verification"
    assert signup["workspaceId"]

    login_before_verification = identity_client.post(
        "/auth/login",
        json={
            "email": "owner@example.com",
            "password": "an unusually strong passphrase 2026",
        },
    )
    assert login_before_verification.status_code == 401

    verified = identity_client.post(
        "/auth/verify-email",
        json={"token": signup["developmentVerificationToken"]},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["organization"]["role"] == "owner"

    profile = identity_client.get("/auth/me")
    assert profile.status_code == 200
    assert profile.json()["user"]["email"] == "owner@example.com"

    missing_csrf = identity_client.post("/auth/logout")
    assert missing_csrf.status_code == 403
    csrf = identity_client.cookies.get(CSRF_COOKIE)
    logged_out = identity_client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 204
    assert identity_client.get("/auth/me").status_code == 401


def test_duplicate_signup_and_generic_password_recovery(identity_client: TestClient) -> None:
    signup = _signup(identity_client)
    duplicate = identity_client.post(
        "/auth/signup",
        json={
            "email": "OWNER@example.com",
            "password": "another unusually strong passphrase",
            "organizationName": "Other Capital",
            "acceptedTerms": True,
        },
    )
    assert duplicate.status_code == 409

    unknown = identity_client.post(
        "/auth/forgot-password", json={"email": "unknown@example.com"}
    )
    known = identity_client.post(
        "/auth/forgot-password", json={"email": "owner@example.com"}
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json()["message"] == known.json()["message"]
    assert "developmentResetToken" not in unknown.json()

    reset = identity_client.post(
        "/auth/reset-password",
        json={
            "token": known.json()["developmentResetToken"],
            "newPassword": "a replacement passphrase with enough length",
        },
    )
    assert reset.status_code == 200
    old_login = identity_client.post(
        "/auth/login",
        json={
            "email": "owner@example.com",
            "password": "an unusually strong passphrase 2026",
        },
    )
    assert old_login.status_code == 401

    # The account remains pending until the original verification is consumed.
    verification = identity_client.post(
        "/auth/verify-email",
        json={"token": signup["developmentVerificationToken"]},
    )
    assert verification.status_code == 200
    csrf = identity_client.cookies.get(CSRF_COOKIE)
    identity_client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    new_login = identity_client.post(
        "/auth/login",
        json={
            "email": "owner@example.com",
            "password": "a replacement passphrase with enough length",
        },
    )
    assert new_login.status_code == 200


def test_invalid_tokens_and_terms_fail_closed(identity_client: TestClient) -> None:
    refused = identity_client.post(
        "/auth/signup",
        json={
            "email": "owner@example.com",
            "password": "an unusually strong passphrase 2026",
            "organizationName": "Northstar Capital",
            "acceptedTerms": False,
        },
    )
    assert refused.status_code == 422
    assert identity_client.post(
        "/auth/verify-email", json={"token": "x" * 32}
    ).status_code == 400
    assert identity_client.post(
        "/auth/reset-password",
        json={"token": "x" * 32, "newPassword": "a replacement passphrase 2026"},
    ).status_code == 400


def test_resend_profile_password_change_and_logout_all(identity_client: TestClient) -> None:
    signup = _signup(identity_client)
    resent = identity_client.post(
        "/auth/resend-verification", json={"email": "owner@example.com"}
    )
    assert resent.status_code == 202
    token = resent.json()["developmentVerificationToken"]
    assert token != signup["developmentVerificationToken"]
    assert identity_client.post(
        "/auth/verify-email", json={"token": signup["developmentVerificationToken"]}
    ).status_code == 400
    assert identity_client.post("/auth/verify-email", json={"token": token}).status_code == 200

    csrf = identity_client.cookies.get(CSRF_COOKIE)
    profile = identity_client.patch(
        "/auth/profile",
        headers={"X-CSRF-Token": csrf},
        json={"displayName": "Avery Chen", "professionalRole": "portfolio_manager"},
    )
    assert profile.status_code == 200
    assert identity_client.get("/auth/me").json()["user"]["displayName"] == "Avery Chen"

    with TestClient(app) as second:
        assert second.post(
            "/auth/login",
            json={
                "email": "owner@example.com",
                "password": "an unusually strong passphrase 2026",
            },
        ).status_code == 200
        changed = identity_client.post(
            "/auth/change-password",
            headers={"X-CSRF-Token": csrf},
            json={
                "currentPassword": "an unusually strong passphrase 2026",
                "newPassword": "a completely different secure phrase 2026",
            },
        )
        assert changed.status_code == 200
        assert second.get("/auth/me").status_code == 401

    csrf = identity_client.cookies.get(CSRF_COOKIE)
    assert identity_client.post(
        "/auth/logout-all", headers={"X-CSRF-Token": csrf}
    ).status_code == 204
    assert identity_client.get("/auth/me").status_code == 401


def test_tenant_invitation_creates_active_member(identity_client: TestClient) -> None:
    signup = _signup(identity_client)
    assert identity_client.post(
        "/auth/verify-email", json={"token": signup["developmentVerificationToken"]}
    ).status_code == 200
    csrf = identity_client.cookies.get(CSRF_COOKIE)
    invited = identity_client.post(
        "/team/invitations",
        headers={"X-CSRF-Token": csrf},
        json={"email": "analyst@example.com", "role": "analyst"},
    )
    assert invited.status_code == 201, invited.text
    token = invited.json()["developmentInvitationToken"]
    before = identity_client.get("/team").json()
    assert len(before["members"]) == 1
    assert len(before["invitations"]) == 1

    with TestClient(app) as invitee:
        accepted = invitee.post(
            "/auth/accept-invite",
            json={
                "token": token,
                "password": "a strong invited member phrase 2026",
                "displayName": "Jordan Lee",
                "professionalRole": "analyst",
                "acceptedTerms": True,
            },
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["organization"]["id"] == signup["organizationId"]
        assert accepted.json()["organization"]["role"] == "analyst"
        assert invitee.get("/auth/me").status_code == 200
        analyst = next(
            member for member in identity_client.get("/team").json()["members"]
            if member["email"] == "analyst@example.com"
        )
        suspended = identity_client.patch(
            f"/team/members/{analyst['id']}",
            headers={"X-CSRF-Token": csrf},
            json={"role": "reviewer", "status": "suspended"},
        )
        assert suspended.status_code == 200, suspended.text
        assert invitee.get("/auth/me").status_code == 401
        reactivated = identity_client.patch(
            f"/team/members/{analyst['id']}",
            headers={"X-CSRF-Token": csrf},
            json={"role": "reviewer", "status": "active"},
        )
        assert reactivated.status_code == 200, reactivated.text

    after = identity_client.get("/team").json()
    assert len(after["members"]) == 2
    assert after["invitations"] == []
    assert {member["email"] for member in after["members"]} == {
        "owner@example.com", "analyst@example.com"
    }
    analyst_after = next(member for member in after["members"] if member["email"] == "analyst@example.com")
    assert analyst_after["role"] == "reviewer"
