"""Tenant-scoped memberships and single-use email invitations."""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from threading import RLock
from uuid import uuid4

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from .auth_api import _set_session_cookies, _session_payload
from .identity import (
    PRIVACY_VERSION,
    TERMS_VERSION,
    Account,
    EmailSender,
    InMemoryIdentityRepository,
    PASSWORD_HASHER,
    _MemoryUser,
    canonicalize_email,
    development_tokens_exposed,
    get_identity_service,
    hash_token,
    utc_now,
    validate_password,
)
from .operations import current_principal

router = APIRouter(tags=["team"])
LOGGER = logging.getLogger("ambrosia.team")
INVITATION_TTL_DAYS = 7
ROLES = {"viewer", "analyst", "reviewer", "admin"}


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default="analyst", max_length=20)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str | None = Field(default=None, max_length=256)
    displayName: str = Field(default="", max_length=100)
    professionalRole: str = Field(default="other", max_length=40)
    acceptedTerms: bool = False


class MemberUpdate(BaseModel):
    role: str = Field(pattern="^(viewer|analyst|reviewer|admin)$")
    status: str = Field(pattern="^(active|suspended)$")


def _principal():
    principal = current_principal()
    if not principal or not principal.organization_id:
        raise HTTPException(status_code=401, detail="Tenant-bound account required")
    return principal


@dataclass
class _MemoryInvitation:
    id: str
    organization_id: str
    organization_name: str
    workspace_id: str
    email: str
    email_canonical: str
    role: str
    token_hash: str
    invited_by: str
    expires_at: object
    accepted_at: object | None = None
    revoked_at: object | None = None


class TeamService:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.invitations: dict[str, _MemoryInvitation] = {}
        self.lock = RLock()

    @property
    def durable(self) -> bool:
        return bool(self.database_url)

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def list_team(self, organization_id: str) -> dict:
        if self.durable:
            with self._connect() as connection:
                members = connection.execute(
                    """
                    SELECT u.id, u.email, u.display_name, u.professional_role,
                      m.role, m.status, m.created_at
                    FROM organization_memberships m
                    JOIN users u ON u.id = m.user_id
                    WHERE m.organization_id = %s
                    ORDER BY m.created_at
                    """,
                    (organization_id,),
                ).fetchall()
                invitations = connection.execute(
                    """
                    SELECT id, email_canonical AS email, role, created_at, expires_at
                    FROM organization_invitations
                    WHERE organization_id = %s AND accepted_at IS NULL
                      AND revoked_at IS NULL AND expires_at > now()
                    ORDER BY created_at DESC
                    """,
                    (organization_id,),
                ).fetchall()
            return {"members": [dict(row) for row in members], "invitations": [dict(row) for row in invitations]}

        repository = get_identity_service().repository
        members = []
        if isinstance(repository, InMemoryIdentityRepository):
            for user in repository.users.values():
                if user.account.organization_id == organization_id:
                    members.append({
                        "id": user.account.user_id, "email": user.account.email,
                        "display_name": user.display_name,
                        "professional_role": user.professional_role,
                        "role": user.account.role, "status": user.status,
                        "created_at": None,
                    })
        with self.lock:
            invitations = [
                {
                    "id": item.id, "email": item.email, "role": item.role,
                    "created_at": None, "expires_at": item.expires_at,
                }
                for item in self.invitations.values()
                if item.organization_id == organization_id
                and item.accepted_at is None and item.revoked_at is None
                and item.expires_at > utc_now()
            ]
        return {"members": members, "invitations": invitations}

    def create_invitation(
        self, organization_id: str, organization_name: str, invited_by: str,
        email: str, role: str,
    ) -> tuple[dict, str]:
        display, canonical = canonicalize_email(email)
        if role not in ROLES:
            raise ValueError("Select a valid team role")
        invitation_id = str(uuid4())
        token = secrets.token_urlsafe(40)
        expires = utc_now() + timedelta(days=INVITATION_TTL_DAYS)
        if self.durable:
            with self._connect() as connection:
                with connection.transaction():
                    duplicate = connection.execute(
                        """
                        SELECT 1 FROM organization_memberships m JOIN users u ON u.id = m.user_id
                        WHERE m.organization_id = %s AND u.email_canonical = %s
                          AND m.status = 'active'
                        """,
                        (organization_id, canonical),
                    ).fetchone()
                    if duplicate:
                        raise ValueError("This person is already an active member")
                    connection.execute(
                        """
                        UPDATE organization_invitations SET revoked_at = now()
                        WHERE organization_id = %s AND email_canonical = %s
                          AND accepted_at IS NULL AND revoked_at IS NULL
                        """,
                        (organization_id, canonical),
                    )
                    connection.execute(
                        """
                        INSERT INTO organization_invitations (
                          id, organization_id, email_canonical, role, token_hash,
                          invited_by_user_id, expires_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            invitation_id, organization_id, canonical, role,
                            hash_token(token), invited_by, expires,
                        ),
                    )
        else:
            repository = get_identity_service().repository
            workspace_id = ""
            if isinstance(repository, InMemoryIdentityRepository):
                inviter = repository._find_user_id(invited_by)
                workspace_id = inviter.account.workspace_id
            with self.lock:
                for item in self.invitations.values():
                    if item.organization_id == organization_id and item.email_canonical == canonical:
                        item.revoked_at = utc_now()
                self.invitations[hash_token(token)] = _MemoryInvitation(
                    invitation_id, organization_id, organization_name, workspace_id,
                    display, canonical, role, hash_token(token), invited_by, expires,
                )
        return {
            "id": invitation_id, "email": display, "role": role,
            "expiresAt": expires.isoformat(),
        }, token

    def revoke_invitation(self, organization_id: str, invitation_id: str) -> bool:
        if self.durable:
            with self._connect() as connection:
                result = connection.execute(
                    """
                    UPDATE organization_invitations SET revoked_at = now()
                    WHERE id = %s AND organization_id = %s AND accepted_at IS NULL
                      AND revoked_at IS NULL
                    """,
                    (invitation_id, organization_id),
                )
            return result.rowcount == 1
        with self.lock:
            for item in self.invitations.values():
                if item.id == invitation_id and item.organization_id == organization_id:
                    item.revoked_at = utc_now()
                    return True
        return False

    def update_member(
        self, organization_id: str, actor_user_id: str, member_user_id: str,
        role: str, member_status: str,
    ) -> bool:
        if member_user_id == actor_user_id and member_status != "active":
            raise ValueError("You cannot suspend your own membership")
        if self.durable:
            with self._connect() as connection:
                with connection.transaction():
                    member = connection.execute(
                        """
                        SELECT role, status FROM organization_memberships
                        WHERE organization_id = %s AND user_id = %s FOR UPDATE
                        """,
                        (organization_id, member_user_id),
                    ).fetchone()
                    if not member:
                        return False
                    if member["role"] == "owner":
                        raise ValueError("The organization owner cannot be changed here")
                    connection.execute(
                        """
                        UPDATE organization_memberships
                        SET role = %s, status = %s, updated_at = now()
                        WHERE organization_id = %s AND user_id = %s
                        """,
                        (role, member_status, organization_id, member_user_id),
                    )
                    if member_status == "suspended":
                        connection.execute(
                            """
                            UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'membership_suspended'
                            WHERE organization_id = %s AND user_id = %s AND revoked_at IS NULL
                            """,
                            (organization_id, member_user_id),
                        )
                    connection.execute(
                        """
                        INSERT INTO auth_events (organization_id, user_id, event_type, detail)
                        VALUES (%s, %s, 'membership_updated', %s::jsonb)
                        """,
                        (
                            organization_id, member_user_id,
                            json.dumps({"role": role, "status": member_status, "actor": actor_user_id}),
                        ),
                    )
            return True
        repository = get_identity_service().repository
        if not isinstance(repository, InMemoryIdentityRepository):
            return False
        with repository.lock:
            try:
                user = repository._find_user_id(member_user_id)
            except StopIteration:
                return False
            if user.account.organization_id != organization_id:
                return False
            if user.account.role == "owner":
                raise ValueError("The organization owner cannot be changed here")
            user.status = member_status
            user.account = Account(
                user.account.user_id, user.account.email, member_status,
                user.account.organization_id, user.account.organization_name,
                role, user.account.workspace_id, user.display_name,
                user.professional_role,
            )
            if member_status == "suspended":
                repository.revoke_all_sessions(member_user_id, "membership_suspended", utc_now())
        return True

    def accept(self, body: InvitationAccept, principal) -> Account | None:
        digest = hash_token(body.token)
        now = utc_now()
        if self.durable:
            with self._connect() as connection:
                with connection.transaction():
                    invitation = connection.execute(
                        """
                        SELECT i.*, o.name AS organization_name
                        FROM organization_invitations i
                        JOIN organizations o ON o.id = i.organization_id AND o.status = 'active'
                        WHERE i.token_hash = %s AND i.accepted_at IS NULL
                          AND i.revoked_at IS NULL AND i.expires_at > %s
                        FOR UPDATE
                        """,
                        (digest, now),
                    ).fetchone()
                    if not invitation:
                        return None
                    user = connection.execute(
                        "SELECT * FROM users WHERE email_canonical = %s AND status <> 'deleted'",
                        (invitation["email_canonical"],),
                    ).fetchone()
                    if user:
                        if not principal or principal.subject != str(user["id"]):
                            raise PermissionError("Sign in with the invited email before accepting")
                        user_id = str(user["id"])
                        display_name = str(user["display_name"])
                        professional_role = str(user["professional_role"])
                    else:
                        if not body.password or not body.acceptedTerms:
                            raise ValueError("A password and policy acceptance are required")
                        validate_password(body.password, email=str(invitation["email_canonical"]))
                        if body.professionalRole not in {
                            "analyst", "portfolio_manager", "risk", "cio_founder", "other"
                        }:
                            raise ValueError("Select a valid professional role")
                        user_id = str(uuid4())
                        display_name = " ".join(body.displayName.split()).strip()
                        professional_role = body.professionalRole
                        connection.execute(
                            """
                            INSERT INTO users (
                              id, email, email_canonical, display_name, professional_role,
                              password_hash, status, email_verified_at, terms_version,
                              privacy_version, terms_accepted_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
                            """,
                            (
                                user_id, invitation["email_canonical"], invitation["email_canonical"],
                                display_name, professional_role, PASSWORD_HASHER.hash(body.password),
                                now, TERMS_VERSION, PRIVACY_VERSION, now,
                            ),
                        )
                        connection.execute(
                            """
                            INSERT INTO terms_acceptances
                              (user_id, terms_version, privacy_version, accepted_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (user_id, TERMS_VERSION, PRIVACY_VERSION, now),
                        )
                    connection.execute(
                        """
                        INSERT INTO organization_memberships (
                          organization_id, user_id, role, status, invited_by_user_id
                        ) VALUES (%s, %s, %s, 'active', %s)
                        ON CONFLICT (organization_id, user_id) DO UPDATE SET
                          role = EXCLUDED.role, status = 'active', updated_at = now()
                        """,
                        (
                            invitation["organization_id"], user_id, invitation["role"],
                            invitation["invited_by_user_id"],
                        ),
                    )
                    connection.execute(
                        "UPDATE organization_invitations SET accepted_at = %s WHERE id = %s",
                        (now, invitation["id"]),
                    )
                    connection.execute(
                        "SELECT set_config('app.current_organization_id', %s, true)",
                        (str(invitation["organization_id"]),),
                    )
                    workspace = connection.execute(
                        "SELECT id FROM workspaces WHERE organization_id = %s ORDER BY created_at LIMIT 1",
                        (invitation["organization_id"],),
                    ).fetchone()
                    connection.execute(
                        """
                        INSERT INTO auth_events (organization_id, user_id, event_type, detail)
                        VALUES (%s, %s, 'invitation_accepted', %s::jsonb)
                        """,
                        (
                            invitation["organization_id"], user_id,
                            json.dumps({"invitationId": str(invitation["id"])}),
                        ),
                    )
                    if not workspace:
                        raise RuntimeError("Invited organization has no workspace")
                    return Account(
                        user_id=user_id, email=str(invitation["email_canonical"]), status="active",
                        organization_id=str(invitation["organization_id"]),
                        organization_name=str(invitation["organization_name"]),
                        role=str(invitation["role"]), workspace_id=str(workspace["id"]),
                        display_name=display_name, professional_role=professional_role,
                    )

        with self.lock:
            invitation = self.invitations.get(digest)
            if not invitation or invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= now:
                return None
            repository = get_identity_service().repository
            if not isinstance(repository, InMemoryIdentityRepository):
                raise RuntimeError("Memory identity repository unavailable")
            user = repository.users.get(invitation.email_canonical)
            if user:
                if not principal or principal.subject != user.account.user_id:
                    raise PermissionError("Sign in with the invited email before accepting")
                user_id = user.account.user_id
            else:
                if not body.password or not body.acceptedTerms:
                    raise ValueError("A password and policy acceptance are required")
                validate_password(body.password, email=invitation.email_canonical)
                user_id = str(uuid4())
                account = Account(
                    user_id, invitation.email, "active", invitation.organization_id,
                    invitation.organization_name, invitation.role, invitation.workspace_id,
                    " ".join(body.displayName.split()).strip(), body.professionalRole,
                )
                user = _MemoryUser(
                    account, invitation.email_canonical, PASSWORD_HASHER.hash(body.password),
                    status="active", display_name=account.display_name,
                    professional_role=account.professional_role,
                )
                repository.users[invitation.email_canonical] = user
            user.account = Account(
                user_id, invitation.email, "active", invitation.organization_id,
                invitation.organization_name, invitation.role, invitation.workspace_id,
                user.display_name, user.professional_role,
            )
            invitation.accepted_at = now
            return user.account


team_service = TeamService()


def reset_team_service() -> None:
    global team_service
    team_service = TeamService()


@router.get("/team")
def team() -> dict:
    principal = _principal()
    return team_service.list_team(principal.organization_id)


@router.post("/team/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(body: InvitationCreate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    try:
        invitation, token = team_service.create_invitation(
            principal.organization_id, principal.organization_name, principal.subject,
            body.email, body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        EmailSender().send_invitation(body.email, token, principal.organization_name)
        invitation["deliveryStatus"] = "sent"
    except Exception:
        LOGGER.exception("invitation email delivery failed after invitation creation")
        invitation["deliveryStatus"] = "retry_required"
    if development_tokens_exposed():
        invitation["developmentInvitationToken"] = token
    return invitation


@router.delete("/team/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    if not team_service.revoke_invitation(principal.organization_id, invitation_id):
        raise HTTPException(status_code=404, detail="Invitation not found")
    return {"revoked": True}


@router.patch("/team/members/{member_user_id}")
def update_member(member_user_id: str, body: MemberUpdate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    try:
        updated = team_service.update_member(
            principal.organization_id, principal.subject, member_user_id,
            body.role, body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"updated": True}


@router.post("/auth/accept-invite")
def accept_invitation(body: InvitationAccept, request: Request, response: Response) -> dict:
    principal = getattr(request.state, "principal", None)
    try:
        account = team_service.accept(body, principal)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not account:
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
    if principal and principal.auth_method == "session":
        get_identity_service().repository.revoke_session(
            principal.session_id, principal.subject, "organization_switched", utc_now()
        )
    issued = get_identity_service().issue_session(
        account, user_agent=request.headers.get("user-agent"),
        remote_ip=request.client.host if request.client else None,
    )
    _set_session_cookies(response, issued)
    return _session_payload(issued)
