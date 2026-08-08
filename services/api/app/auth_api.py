"""Public account lifecycle and authenticated profile/session endpoints."""

from __future__ import annotations

import os
from datetime import datetime

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from .identity import (
    CSRF_COOKIE,
    IssuedSession,
    get_identity_service,
    is_production,
    session_cookie_name,
    utc_now,
)

router = APIRouter(prefix="/auth", tags=["identity"])


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    organizationName: str = Field(min_length=2, max_length=120)
    displayName: str = Field(default="", max_length=100)
    professionalRole: str = Field(default="other", max_length=40)
    acceptedTerms: bool


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    newPassword: str = Field(min_length=1, max_length=256)


class ProfileUpdateRequest(BaseModel):
    displayName: str = Field(default="", max_length=100)
    professionalRole: str = Field(default="other", max_length=40)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=256)
    newPassword: str = Field(min_length=1, max_length=256)


def _remote_ip(request: Request) -> str | None:
    # Only trust the immediate peer here. ALB should overwrite forwarded headers;
    # the application does not parse arbitrary client-supplied chains.
    return request.client.host if request.client else None


def _set_session_cookies(response: Response, issued: IssuedSession) -> None:
    secure = is_production()
    csrf_domain = os.getenv("AUTH_CSRF_COOKIE_DOMAIN", "").strip() or None
    max_age = max(0, int((issued.identity.absolute_expires_at - datetime.now(
        issued.identity.absolute_expires_at.tzinfo
    )).total_seconds()))
    response.set_cookie(
        key=session_cookie_name(),
        value=issued.token,
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=issued.csrf_token,
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
        domain=csrf_domain,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(session_cookie_name(), path="/", secure=is_production(), httponly=True)
    response.delete_cookie(
        CSRF_COOKIE, path="/", secure=is_production(), httponly=False,
        domain=os.getenv("AUTH_CSRF_COOKIE_DOMAIN", "").strip() or None,
    )


def _identity(request: Request):
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.auth_method != "session":
        raise HTTPException(status_code=401, detail="Authenticated account session required")
    return principal


def _session_payload(issued: IssuedSession) -> dict:
    identity = issued.identity
    return {
        "user": {"id": identity.user_id, "email": identity.email},
        "organization": {
            "id": identity.organization_id,
            "name": identity.organization_name,
            "role": identity.role,
        },
        "session": {
            "id": identity.session_id,
            "expiresAt": identity.expires_at.isoformat(),
            "absoluteExpiresAt": identity.absolute_expires_at.isoformat(),
        },
    }


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest) -> dict:
    try:
        account, verification_token, delivered = get_identity_service().signup(
            email=body.email,
            password=body.password,
            organization_name=body.organizationName,
            accepted_terms=body.acceptedTerms,
            display_name=body.displayName,
            professional_role=body.professionalRole,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=409,
            detail="An account for this email already exists. Sign in or reset the password.",
        ) from exc
    payload = {
        "status": "pending_verification",
        "message": (
            "Check your email to verify the account."
            if delivered else
            "Your workspace was created, but email delivery failed. Use resend verification."
        ),
        "deliveryStatus": "sent" if delivered else "retry_required",
        "userId": account.user_id,
        "organizationId": account.organization_id,
        "workspaceId": account.workspace_id,
    }
    if not is_production() and os.getenv("AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true").lower() == "true":
        payload["developmentVerificationToken"] = verification_token
    return payload


@router.post("/verify-email")
def verify_email(body: TokenRequest, request: Request, response: Response) -> dict:
    issued = get_identity_service().verify_email(
        body.token,
        user_agent=request.headers.get("user-agent"),
        remote_ip=_remote_ip(request),
    )
    if not issued:
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    _set_session_cookies(response, issued)
    return _session_payload(issued)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(body: ForgotPasswordRequest) -> dict:
    token = get_identity_service().resend_verification(body.email)
    payload = {"message": "If an unverified account exists, a new link has been sent."}
    if token and not is_production() and os.getenv(
        "AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true"
    ).lower() == "true":
        payload["developmentVerificationToken"] = token
    return payload


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    issued = get_identity_service().login(
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
        remote_ip=_remote_ip(request),
    )
    if not issued:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    _set_session_cookies(response, issued)
    return _session_payload(issued)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordRequest) -> dict:
    token = get_identity_service().forgot_password(body.email)
    payload = {
        "message": "If an eligible account exists, a password-reset email has been sent."
    }
    if token and not is_production() and os.getenv(
        "AUTH_EXPOSE_DEVELOPMENT_TOKENS", "true"
    ).lower() == "true":
        payload["developmentResetToken"] = token
    return payload


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, response: Response) -> dict:
    try:
        changed = get_identity_service().reset_password(body.token, body.newPassword)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    _clear_session_cookies(response)
    return {"status": "password_updated", "message": "Sign in with your new password."}


@router.get("/me")
def me(request: Request) -> dict:
    principal = _identity(request)
    profile = get_identity_service().repository.profile(principal.subject) or {}
    return {
        "user": {
            "id": principal.subject,
            "email": principal.email,
            "displayName": profile.get("display_name", ""),
            "professionalRole": profile.get("professional_role", "other"),
        },
        "organization": {
            "id": principal.organization_id,
            "name": principal.organization_name,
            "role": principal.role,
        },
        "session": {"id": principal.session_id},
    }


@router.patch("/profile")
def update_profile(body: ProfileUpdateRequest, request: Request) -> dict:
    principal = _identity(request)
    display_name = " ".join(body.displayName.split()).strip()
    if body.professionalRole not in {
        "analyst", "portfolio_manager", "risk", "cio_founder", "other"
    }:
        raise HTTPException(status_code=422, detail="Select a valid professional role")
    profile = get_identity_service().repository.update_profile(
        principal.subject, display_name, body.professionalRole
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "user": {
            "id": str(profile["id"]), "email": profile["email"],
            "displayName": profile["display_name"],
            "professionalRole": profile["professional_role"],
        }
    }


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request) -> dict:
    principal = _identity(request)
    try:
        changed = get_identity_service().change_password(
            email=principal.email,
            user_id=principal.subject,
            session_id=principal.session_id,
            current_password=body.currentPassword,
            new_password=body.newPassword,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return {"status": "password_updated", "otherSessionsRevoked": True}


@router.get("/sessions")
def sessions(request: Request) -> dict:
    principal = _identity(request)
    rows = get_identity_service().repository.list_sessions(
        principal.subject, utc_now()
    )
    return {
        "sessions": [
            {
                "id": str(row["id"]),
                "current": str(row["id"]) == principal.session_id,
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "expiresAt": row["expires_at"].isoformat(),
                "absoluteExpiresAt": row["absolute_expires_at"].isoformat(),
                "ipPrefix": row["ip_prefix"],
            }
            for row in rows
        ]
    }


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, request: Request, response: Response) -> dict:
    principal = _identity(request)
    revoked = get_identity_service().repository.revoke_session(
        session_id, principal.subject, "user_revoked", utc_now()
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id == principal.session_id:
        _clear_session_cookies(response)
    return {"revoked": True, "sessionId": session_id}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> Response:
    principal = _identity(request)
    get_identity_service().repository.revoke_session(
        principal.session_id, principal.subject, "logout", utc_now()
    )
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(request: Request, response: Response) -> Response:
    principal = _identity(request)
    get_identity_service().repository.revoke_all_sessions(
        principal.subject, "logout_all", utc_now()
    )
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
