from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.identity import (
    CSRF_COOKIE,
    canonicalize_email,
    reset_identity_service,
    validate_password,
)
from app.main import app
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
