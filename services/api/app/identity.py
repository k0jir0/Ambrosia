"""Database-backed first-party identity and opaque session management.

PostgreSQL is authoritative whenever DATABASE_URL is configured. Development
without PostgreSQL uses an isolated in-memory repository so the public account
flow remains testable; production already requires durable persistence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol
from urllib.parse import quote
from uuid import uuid4

import boto3
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from psycopg.rows import dict_row

LOGGER = logging.getLogger("ambrosia.identity")

TERMS_VERSION = "2026-08-07"
PRIVACY_VERSION = "2026-08-07"
SESSION_COOKIE_PRODUCTION = "__Host-ambrosia_session"
SESSION_COOKIE_DEVELOPMENT = "ambrosia_session"
CSRF_COOKIE = "ambrosia_csrf"
PASSWORD_MIN_LENGTH = 15
PASSWORD_MAX_LENGTH = 256
SESSION_IDLE_HOURS = 12
SESSION_ABSOLUTE_DAYS = 30
TOKEN_TTL_MINUTES = 30
LOCK_THRESHOLD = 5
LOCK_MINUTES = 15

COMMON_PASSWORDS = {
    "123456789012345",
    "ambrosiaambrosia",
    "correcthorsebatterystaple",
    "letmeinletmeinletmein",
    "passwordpassword",
    "qwertyuiopasdfgh",
}

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonicalize_email(value: str) -> tuple[str, str]:
    display = unicodedata.normalize("NFKC", value).strip()
    if len(display) > 320 or display.count("@") != 1:
        raise ValueError("Enter a valid email address")
    local, domain = display.rsplit("@", 1)
    if not local or len(local) > 64 or not domain or any(char.isspace() for char in display):
        raise ValueError("Enter a valid email address")
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Enter a valid email address") from exc
    if "." not in ascii_domain and ascii_domain != "localhost":
        raise ValueError("Enter a valid email address")
    canonical = f"{local.casefold()}@{ascii_domain.casefold()}"
    return display, canonical


def validate_password(password: str, *, email: str | None = None) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be no more than {PASSWORD_MAX_LENGTH} characters")
    normalized = unicodedata.normalize("NFKC", password).casefold()
    if normalized in COMMON_PASSWORDS:
        raise ValueError("Choose a password that is not commonly used")
    if email:
        local = email.split("@", 1)[0].casefold()
        if len(local) >= 4 and local in normalized:
            raise ValueError("Password must not contain your email name")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return (slug[:40] or "workspace") + "-" + uuid4().hex[:8]


def _environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    return _environment() in {"production", "staging"}


def _flag_enabled(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def staging_console_delivery_enabled() -> bool:
    return (
        _environment() == "staging"
        and os.getenv("AUTH_EMAIL_MODE", "").strip().lower() == "console"
        and _flag_enabled("AUTH_ALLOW_STAGING_CONSOLE_DELIVERY")
    )


def development_tokens_exposed() -> bool:
    return _environment() == "development" and _flag_enabled(
        "AUTH_EXPOSE_DEVELOPMENT_TOKENS",
        default=True,
    )


def verification_tokens_exposed() -> bool:
    return development_tokens_exposed() or (
        staging_console_delivery_enabled()
        and _flag_enabled("AUTH_EXPOSE_DEVELOPMENT_TOKENS")
    )


def session_cookie_name() -> str:
    return SESSION_COOKIE_PRODUCTION if is_production() else SESSION_COOKIE_DEVELOPMENT


def _token_pepper() -> bytes:
    pepper = os.getenv("AUTH_TOKEN_PEPPER", "").strip()
    if is_production() and len(pepper) < 32:
        raise RuntimeError("AUTH_TOKEN_PEPPER must contain at least 32 characters")
    return (pepper or "ambrosia-development-token-pepper-not-for-production").encode()


def hash_token(token: str) -> str:
    return hmac.new(_token_pepper(), token.encode(), hashlib.sha256).hexdigest()


def hash_metadata(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def ip_prefix(value: str | None) -> str | None:
    if not value:
        return None
    if ":" in value:
        return ":".join(value.split(":")[:4]) + "::/64"
    parts = value.split(".")
    return ".".join(parts[:3]) + ".0/24" if len(parts) == 4 else None


@dataclass(frozen=True)
class Account:
    user_id: str
    email: str
    status: str
    organization_id: str
    organization_name: str
    role: str
    workspace_id: str
    display_name: str = ""
    professional_role: str = "other"


@dataclass(frozen=True)
class SessionIdentity:
    session_id: str
    user_id: str
    email: str
    organization_id: str
    organization_name: str
    role: str
    csrf_hash: str
    expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True)
class IssuedSession:
    identity: SessionIdentity
    token: str
    csrf_token: str


@dataclass(frozen=True)
class TokenDelivery:
    email: str
    token: str


class IdentityRepository(Protocol):
    def create_account(
        self, *, email: str, canonical_email: str, password_hash: str,
        organization_name: str, display_name: str, professional_role: str,
        terms_version: str, privacy_version: str, token_hash: str,
    ) -> Account: ...

    def consume_verification(self, token_hash: str, now: datetime) -> Account | None: ...
    def login_record(self, canonical_email: str) -> dict | None: ...
    def record_login_failure(self, user_id: str, now: datetime) -> None: ...
    def record_login_success(self, user_id: str, now: datetime) -> None: ...
    def create_session(
        self, *, account: Account, token_hash: str, csrf_hash: str,
        user_agent_hash: str | None, ip_network: str | None, now: datetime,
    ) -> SessionIdentity: ...
    def get_session(self, token_hash: str, now: datetime) -> SessionIdentity | None: ...
    def list_sessions(self, user_id: str, now: datetime) -> list[dict]: ...
    def revoke_session(self, session_id: str, user_id: str, reason: str, now: datetime) -> bool: ...
    def revoke_all_sessions(self, user_id: str, reason: str, now: datetime) -> None: ...
    def create_password_reset(self, canonical_email: str, token_hash: str, now: datetime) -> str | None: ...
    def consume_password_reset(self, token_hash: str, password_hash: str, now: datetime) -> bool: ...
    def create_verification(self, canonical_email: str, token_hash: str, now: datetime) -> str | None: ...
    def profile(self, user_id: str) -> dict | None: ...
    def update_profile(self, user_id: str, display_name: str, professional_role: str) -> dict | None: ...
    def change_password(
        self, user_id: str, password_hash: str, keep_session_id: str, now: datetime
    ) -> bool: ...
    def healthcheck(self) -> None: ...


class PostgresIdentityRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def healthcheck(self) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT to_regclass('public.users') AS users").fetchone()
            if not row or row["users"] is None:
                raise RuntimeError("identity_schema_missing")

    def _account_for_user(self, cursor, user_id: str) -> Account | None:
        row = cursor.execute(
            """
            SELECT u.id AS user_id, u.email, u.status,
                   u.display_name, u.professional_role,
                   o.id AS organization_id, o.name AS organization_name,
                   m.role
            FROM users u
            JOIN organization_memberships m ON m.user_id = u.id AND m.status = 'active'
            JOIN organizations o ON o.id = m.organization_id AND o.status = 'active'
            WHERE u.id = %s
            ORDER BY CASE m.role WHEN 'owner' THEN 0 ELSE 1 END, m.created_at
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        cursor.execute(
            "SELECT set_config('app.current_organization_id', %s, true)",
            (str(row["organization_id"]),),
        )
        workspace = cursor.execute(
            """
            SELECT id FROM workspaces
            WHERE organization_id = %s
            ORDER BY created_at LIMIT 1
            """,
            (row["organization_id"],),
        ).fetchone()
        if not workspace:
            return None
        return Account(
            user_id=str(row["user_id"]),
            email=str(row["email"]),
            status=str(row["status"]),
            organization_id=str(row["organization_id"]),
            organization_name=str(row["organization_name"]),
            role=str(row["role"]),
            workspace_id=str(workspace["id"]),
            display_name=str(row["display_name"]),
            professional_role=str(row["professional_role"]),
        )

    def create_account(
        self, *, email: str, canonical_email: str, password_hash: str,
        organization_name: str, display_name: str, professional_role: str,
        terms_version: str, privacy_version: str, token_hash: str,
    ) -> Account:
        now = utc_now()
        organization_id = str(uuid4())
        user_id = str(uuid4())
        workspace_id = str(uuid4())
        with self._connect() as connection:
            with connection.transaction():
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (
                      id, email, email_canonical, display_name, professional_role,
                      password_hash, terms_version, privacy_version, terms_accepted_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id, email, canonical_email, display_name, professional_role,
                        password_hash, terms_version, privacy_version, now,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO terms_acceptances
                      (user_id, terms_version, privacy_version, accepted_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, terms_version, privacy_version, now),
                )
                cursor.execute(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES (%s, %s, %s)
                    """,
                    (organization_id, organization_name, slugify(organization_name)),
                )
                cursor.execute(
                    """
                    INSERT INTO organization_memberships
                      (organization_id, user_id, role, status)
                    VALUES (%s, %s, 'owner', 'active')
                    """,
                    (organization_id, user_id),
                )
                cursor.execute(
                    "SELECT set_config('app.current_organization_id', %s, true)",
                    (organization_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO workspaces
                      (id, organization_id, created_by_user_id, name, is_demo)
                    VALUES (%s, %s, %s, %s, false)
                    """,
                    (workspace_id, organization_id, user_id, f"{organization_name} Decisions"),
                )
                cursor.execute(
                    """
                    INSERT INTO workspace_guided_samples
                      (organization_id, workspace_id, sample_id, sample_version)
                    VALUES (%s, %s, 'ambrosia-first-decision', 1)
                    """,
                    (organization_id, workspace_id),
                )
                cursor.execute(
                    """
                    INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, token_hash, now + timedelta(minutes=TOKEN_TTL_MINUTES)),
                )
                cursor.execute(
                    """
                    INSERT INTO auth_events (organization_id, user_id, event_type, detail)
                    VALUES (%s, %s, 'signup_created', %s::jsonb)
                    """,
                    (organization_id, user_id, json.dumps({"termsVersion": terms_version})),
                )
        return Account(
            user_id=user_id,
            email=email,
            status="pending_verification",
            organization_id=organization_id,
            organization_name=organization_name,
            role="owner",
            workspace_id=workspace_id,
            display_name=display_name,
            professional_role=professional_role,
        )

    def consume_verification(self, token_hash: str, now: datetime) -> Account | None:
        with self._connect() as connection:
            with connection.transaction():
                cursor = connection.cursor()
                row = cursor.execute(
                    """
                    SELECT id, user_id FROM email_verification_tokens
                    WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s
                    FOR UPDATE
                    """,
                    (token_hash, now),
                ).fetchone()
                if not row:
                    return None
                cursor.execute(
                    "UPDATE email_verification_tokens SET used_at = %s WHERE id = %s",
                    (now, row["id"]),
                )
                cursor.execute(
                    """
                    UPDATE users SET status = 'active', email_verified_at = %s,
                      updated_at = %s WHERE id = %s
                    """,
                    (now, now, row["user_id"]),
                )
                account = self._account_for_user(cursor, str(row["user_id"]))
                if account:
                    cursor.execute(
                        """
                        INSERT INTO auth_events (organization_id, user_id, event_type)
                        VALUES (%s, %s, 'email_verified')
                        """,
                        (account.organization_id, account.user_id),
                    )
                return account

    def login_record(self, canonical_email: str) -> dict | None:
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                SELECT u.id AS user_id, u.email, u.email_canonical, u.password_hash,
                       u.display_name, u.professional_role, u.status, u.locked_until,
                       o.id AS organization_id,
                       o.name AS organization_name, m.role
                FROM users u
                LEFT JOIN organization_memberships m
                  ON m.user_id = u.id AND m.status = 'active'
                LEFT JOIN organizations o ON o.id = m.organization_id AND o.status = 'active'
                WHERE u.email_canonical = %s
                ORDER BY CASE m.role WHEN 'owner' THEN 0 ELSE 1 END, m.created_at
                LIMIT 1
                """,
                    (canonical_email,),
                ).fetchone()
                if not row or not row.get("organization_id"):
                    return dict(row) if row else None
                connection.execute(
                    "SELECT set_config('app.current_organization_id', %s, true)",
                    (str(row["organization_id"]),),
                )
                workspace = connection.execute(
                    """
                    SELECT id FROM workspaces
                    WHERE organization_id = %s
                    ORDER BY created_at LIMIT 1
                    """,
                    (row["organization_id"],),
                ).fetchone()
                result = dict(row)
                result["workspace_id"] = workspace["id"] if workspace else None
                return result

    def record_login_failure(self, user_id: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE users SET
                  failed_login_count = failed_login_count + 1,
                  locked_until = CASE WHEN failed_login_count + 1 >= %s
                    THEN %s ELSE locked_until END,
                  status = CASE WHEN failed_login_count + 1 >= %s
                    THEN 'locked' ELSE status END,
                  updated_at = %s
                WHERE id = %s
                """,
                (LOCK_THRESHOLD, now + timedelta(minutes=LOCK_MINUTES), LOCK_THRESHOLD, now, user_id),
            )

    def record_login_success(self, user_id: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE users SET failed_login_count = 0, locked_until = NULL,
                  status = CASE WHEN status = 'locked' THEN 'active' ELSE status END,
                  last_login_at = %s, updated_at = %s WHERE id = %s
                """,
                (now, now, user_id),
            )

    def create_session(
        self, *, account: Account, token_hash: str, csrf_hash: str,
        user_agent_hash: str | None, ip_network: str | None, now: datetime,
    ) -> SessionIdentity:
        session_id = str(uuid4())
        expires = now + timedelta(hours=SESSION_IDLE_HOURS)
        absolute = now + timedelta(days=SESSION_ABSOLUTE_DAYS)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_sessions (
                  id, user_id, organization_id, token_hash, csrf_hash,
                  user_agent_hash, ip_prefix, expires_at, absolute_expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (session_id, account.user_id, account.organization_id, token_hash,
                 csrf_hash, user_agent_hash, ip_network, expires, absolute),
            )
        return SessionIdentity(
            session_id=session_id,
            user_id=account.user_id,
            email=account.email,
            organization_id=account.organization_id,
            organization_name=account.organization_name,
            role=account.role,
            csrf_hash=csrf_hash,
            expires_at=expires,
            absolute_expires_at=absolute,
        )

    def get_session(self, token_hash: str, now: datetime) -> SessionIdentity | None:
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT s.id AS session_id, u.id AS user_id, u.email,
                           s.organization_id, o.name AS organization_name,
                           m.role, s.csrf_hash, s.expires_at, s.absolute_expires_at,
                           s.last_seen_at
                    FROM user_sessions s
                    JOIN users u ON u.id = s.user_id AND u.status = 'active'
                    JOIN organizations o ON o.id = s.organization_id AND o.status = 'active'
                    JOIN organization_memberships m
                      ON m.user_id = u.id AND m.organization_id = s.organization_id
                      AND m.status = 'active'
                    WHERE s.token_hash = %s AND s.revoked_at IS NULL
                      AND s.expires_at > %s AND s.absolute_expires_at > %s
                    """,
                    (token_hash, now, now),
                ).fetchone()
                if not row:
                    return None
                if row["last_seen_at"] < now - timedelta(minutes=5):
                    new_expiry = min(
                        now + timedelta(hours=SESSION_IDLE_HOURS), row["absolute_expires_at"]
                    )
                    connection.execute(
                        "UPDATE user_sessions SET last_seen_at = %s, expires_at = %s WHERE id = %s",
                        (now, new_expiry, row["session_id"]),
                    )
                    row["expires_at"] = new_expiry
        return SessionIdentity(**{
            key: (str(row[key]) if key not in {"expires_at", "absolute_expires_at"} else row[key])
            for key in SessionIdentity.__dataclass_fields__
        })

    def list_sessions(self, user_id: str, now: datetime) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, last_seen_at, expires_at, absolute_expires_at,
                       user_agent_hash, ip_prefix
                FROM user_sessions WHERE user_id = %s AND revoked_at IS NULL
                  AND expires_at > %s AND absolute_expires_at > %s
                ORDER BY last_seen_at DESC
                """,
                (user_id, now, now),
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_session(self, session_id: str, user_id: str, reason: str, now: datetime) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE user_sessions SET revoked_at = %s, revoke_reason = %s
                WHERE id = %s AND user_id = %s AND revoked_at IS NULL
                """,
                (now, reason, session_id, user_id),
            )
        return result.rowcount == 1

    def revoke_all_sessions(self, user_id: str, reason: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE user_sessions SET revoked_at = %s, revoke_reason = %s
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (now, reason, user_id),
            )

    def create_password_reset(self, canonical_email: str, token_hash: str, now: datetime) -> str | None:
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(
                    "SELECT id, email FROM users WHERE email_canonical = %s AND status <> 'deleted'",
                    (canonical_email,),
                ).fetchone()
                if not row:
                    return None
                connection.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (row["id"], token_hash, now + timedelta(minutes=TOKEN_TTL_MINUTES)),
                )
                return str(row["email"])

    def consume_password_reset(self, token_hash: str, password_hash: str, now: datetime) -> bool:
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT id, user_id FROM password_reset_tokens
                    WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s
                    FOR UPDATE
                    """,
                    (token_hash, now),
                ).fetchone()
                if not row:
                    return False
                connection.execute(
                    "UPDATE password_reset_tokens SET used_at = %s WHERE id = %s",
                    (now, row["id"]),
                )
                connection.execute(
                    """
                    UPDATE users SET password_hash = %s, password_changed_at = %s,
                      failed_login_count = 0, locked_until = NULL,
                      status = CASE WHEN email_verified_at IS NULL
                        THEN 'pending_verification' ELSE 'active' END,
                      updated_at = %s WHERE id = %s
                    """,
                    (password_hash, now, now, row["user_id"]),
                )
                connection.execute(
                    """
                    UPDATE user_sessions SET revoked_at = %s, revoke_reason = 'password_reset'
                    WHERE user_id = %s AND revoked_at IS NULL
                    """,
                    (now, row["user_id"]),
                )
                return True

    def create_verification(
        self, canonical_email: str, token_hash: str, now: datetime
    ) -> str | None:
        with self._connect() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT id, email FROM users
                    WHERE email_canonical = %s AND status = 'pending_verification'
                    """,
                    (canonical_email,),
                ).fetchone()
                if not row:
                    return None
                connection.execute(
                    """
                    UPDATE email_verification_tokens SET used_at = %s
                    WHERE user_id = %s AND used_at IS NULL
                    """,
                    (now, row["id"]),
                )
                connection.execute(
                    """
                    INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (row["id"], token_hash, now + timedelta(minutes=TOKEN_TTL_MINUTES)),
                )
                return str(row["email"])

    def profile(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, professional_role, created_at,
                       email_verified_at
                FROM users WHERE id = %s AND status <> 'deleted'
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_profile(
        self, user_id: str, display_name: str, professional_role: str
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE users SET display_name = %s, professional_role = %s,
                  updated_at = now() WHERE id = %s AND status <> 'deleted'
                RETURNING id, email, display_name, professional_role, created_at,
                  email_verified_at
                """,
                (display_name, professional_role, user_id),
            ).fetchone()
        return dict(row) if row else None

    def change_password(
        self, user_id: str, password_hash: str, keep_session_id: str, now: datetime
    ) -> bool:
        with self._connect() as connection:
            with connection.transaction():
                result = connection.execute(
                    """
                    UPDATE users SET password_hash = %s, password_changed_at = %s,
                      updated_at = %s WHERE id = %s AND status = 'active'
                    """,
                    (password_hash, now, now, user_id),
                )
                if result.rowcount != 1:
                    return False
                connection.execute(
                    """
                    UPDATE user_sessions SET revoked_at = %s,
                      revoke_reason = 'password_changed'
                    WHERE user_id = %s AND id <> %s AND revoked_at IS NULL
                    """,
                    (now, user_id, keep_session_id),
                )
                return True


@dataclass
class _MemoryUser:
    account: Account
    canonical_email: str
    password_hash: str
    status: str = "pending_verification"
    failed: int = 0
    locked_until: datetime | None = None
    display_name: str = ""
    professional_role: str = "other"


@dataclass
class InMemoryIdentityRepository:
    users: dict[str, _MemoryUser] = field(default_factory=dict)
    verification: dict[str, tuple[str, datetime]] = field(default_factory=dict)
    resets: dict[str, tuple[str, datetime]] = field(default_factory=dict)
    sessions: dict[str, tuple[SessionIdentity, str]] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)

    def healthcheck(self) -> None:
        return None

    def create_account(
        self, *, email: str, canonical_email: str, password_hash: str,
        organization_name: str, display_name: str, professional_role: str,
        terms_version: str, privacy_version: str, token_hash: str,
    ) -> Account:
        del terms_version, privacy_version
        with self.lock:
            if canonical_email in self.users:
                raise psycopg.errors.UniqueViolation("email already registered")
            account = Account(
                user_id=str(uuid4()), email=email, status="pending_verification",
                organization_id=str(uuid4()), organization_name=organization_name,
                role="owner", workspace_id=str(uuid4()),
                display_name=display_name, professional_role=professional_role,
            )
            self.users[canonical_email] = _MemoryUser(
                account, canonical_email, password_hash,
                display_name=display_name, professional_role=professional_role,
            )
            self.verification[token_hash] = (
                canonical_email, utc_now() + timedelta(minutes=TOKEN_TTL_MINUTES)
            )
            return account

    def consume_verification(self, token_hash: str, now: datetime) -> Account | None:
        with self.lock:
            record = self.verification.pop(token_hash, None)
            if not record or record[1] <= now:
                return None
            user = self.users[record[0]]
            user.status = "active"
            user.account = Account(**{**user.account.__dict__, "status": "active"})
            return user.account

    def login_record(self, canonical_email: str) -> dict | None:
        with self.lock:
            user = self.users.get(canonical_email)
            if not user:
                return None
            return {
                "user_id": user.account.user_id,
                "email": user.account.email,
                "email_canonical": canonical_email,
                "password_hash": user.password_hash,
                "status": user.status,
                "locked_until": user.locked_until,
                "organization_id": user.account.organization_id,
                "organization_name": user.account.organization_name,
                "role": user.account.role,
                "workspace_id": user.account.workspace_id,
            }

    def _find_user_id(self, user_id: str) -> _MemoryUser:
        return next(user for user in self.users.values() if user.account.user_id == user_id)

    def record_login_failure(self, user_id: str, now: datetime) -> None:
        with self.lock:
            user = self._find_user_id(user_id)
            user.failed += 1
            if user.failed >= LOCK_THRESHOLD:
                user.status = "locked"
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)

    def record_login_success(self, user_id: str, now: datetime) -> None:
        del now
        with self.lock:
            user = self._find_user_id(user_id)
            user.failed = 0
            user.locked_until = None
            if user.status == "locked":
                user.status = "active"

    def create_session(
        self, *, account: Account, token_hash: str, csrf_hash: str,
        user_agent_hash: str | None, ip_network: str | None, now: datetime,
    ) -> SessionIdentity:
        del user_agent_hash, ip_network
        identity = SessionIdentity(
            session_id=str(uuid4()), user_id=account.user_id, email=account.email,
            organization_id=account.organization_id,
            organization_name=account.organization_name, role=account.role,
            csrf_hash=csrf_hash, expires_at=now + timedelta(hours=SESSION_IDLE_HOURS),
            absolute_expires_at=now + timedelta(days=SESSION_ABSOLUTE_DAYS),
        )
        with self.lock:
            self.sessions[token_hash] = (identity, token_hash)
        return identity

    def get_session(self, token_hash: str, now: datetime) -> SessionIdentity | None:
        with self.lock:
            record = self.sessions.get(token_hash)
            if not record:
                return None
            identity = record[0]
            if identity.expires_at <= now or identity.absolute_expires_at <= now:
                self.sessions.pop(token_hash, None)
                return None
            return identity

    def list_sessions(self, user_id: str, now: datetime) -> list[dict]:
        with self.lock:
            return [
                {
                    "id": identity.session_id,
                    "created_at": None,
                    "last_seen_at": None,
                    "expires_at": identity.expires_at,
                    "absolute_expires_at": identity.absolute_expires_at,
                    "user_agent_hash": None,
                    "ip_prefix": None,
                }
                for identity, _ in self.sessions.values()
                if identity.user_id == user_id and identity.expires_at > now
            ]

    def revoke_session(self, session_id: str, user_id: str, reason: str, now: datetime) -> bool:
        del reason, now
        with self.lock:
            for token_hash, (identity, _) in list(self.sessions.items()):
                if identity.session_id == session_id and identity.user_id == user_id:
                    self.sessions.pop(token_hash)
                    return True
        return False

    def revoke_all_sessions(self, user_id: str, reason: str, now: datetime) -> None:
        del reason, now
        with self.lock:
            for token_hash, (identity, _) in list(self.sessions.items()):
                if identity.user_id == user_id:
                    self.sessions.pop(token_hash)

    def create_password_reset(self, canonical_email: str, token_hash: str, now: datetime) -> str | None:
        with self.lock:
            user = self.users.get(canonical_email)
            if not user:
                return None
            self.resets[token_hash] = (
                canonical_email, now + timedelta(minutes=TOKEN_TTL_MINUTES)
            )
            return user.account.email

    def consume_password_reset(self, token_hash: str, password_hash: str, now: datetime) -> bool:
        with self.lock:
            record = self.resets.pop(token_hash, None)
            if not record or record[1] <= now:
                return False
            user = self.users[record[0]]
            user.password_hash = password_hash
            user.failed = 0
            user.locked_until = None
            if user.status == "locked":
                user.status = "active"
            self.revoke_all_sessions(user.account.user_id, "password_reset", now)
            return True

    def create_verification(
        self, canonical_email: str, token_hash: str, now: datetime
    ) -> str | None:
        with self.lock:
            user = self.users.get(canonical_email)
            if not user or user.status != "pending_verification":
                return None
            self.verification = {
                digest: value for digest, value in self.verification.items()
                if value[0] != canonical_email
            }
            self.verification[token_hash] = (
                canonical_email, now + timedelta(minutes=TOKEN_TTL_MINUTES)
            )
            return user.account.email

    def profile(self, user_id: str) -> dict | None:
        with self.lock:
            try:
                user = self._find_user_id(user_id)
            except StopIteration:
                return None
            return {
                "id": user.account.user_id, "email": user.account.email,
                "display_name": user.display_name,
                "professional_role": user.professional_role,
                "created_at": None, "email_verified_at": None,
            }

    def update_profile(
        self, user_id: str, display_name: str, professional_role: str
    ) -> dict | None:
        with self.lock:
            try:
                user = self._find_user_id(user_id)
            except StopIteration:
                return None
            user.display_name = display_name
            user.professional_role = professional_role
            return self.profile(user_id)

    def change_password(
        self, user_id: str, password_hash: str, keep_session_id: str, now: datetime
    ) -> bool:
        with self.lock:
            try:
                user = self._find_user_id(user_id)
            except StopIteration:
                return False
            user.password_hash = password_hash
            for token_hash, (identity, _) in list(self.sessions.items()):
                if identity.user_id == user_id and identity.session_id != keep_session_id:
                    self.sessions.pop(token_hash)
            return True


class EmailSender:
    def _public_url(self) -> str:
        return os.getenv("PUBLIC_WEB_URL", "http://127.0.0.1:3000").rstrip("/")

    def send_verification(self, email: str, token: str) -> None:
        self._send(
            email,
            "Verify your Ambrosia account",
            f"Verify your account: {self._public_url()}/verify-email?token={quote(token)}",
        )

    def send_password_reset(self, email: str, token: str) -> None:
        self._send(
            email,
            "Reset your Ambrosia password",
            f"Reset your password: {self._public_url()}/reset-password?token={quote(token)}",
        )

    def send_invitation(self, email: str, token: str, organization_name: str) -> None:
        self._send(
            email,
            f"Join {organization_name} on Ambrosia",
            f"Accept your invitation: {self._public_url()}/accept-invite?token={quote(token)}",
        )

    def _send(self, email: str, subject: str, body: str) -> None:
        mode = os.getenv("AUTH_EMAIL_MODE", "console").strip().lower()
        if mode == "ses":
            source = os.getenv("AUTH_EMAIL_FROM", "").strip()
            if not source:
                raise RuntimeError("AUTH_EMAIL_FROM is required when AUTH_EMAIL_MODE=ses")
            client = boto3.client("sesv2", region_name=os.getenv("AWS_REGION", "us-east-1"))
            request = dict(
                FromEmailAddress=source,
                Destination={"ToAddresses": [email]},
                Content={"Simple": {
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                }},
            )
            configuration_set = os.getenv("AUTH_SES_CONFIGURATION_SET", "").strip()
            if configuration_set:
                request["ConfigurationSetName"] = configuration_set
            client.send_email(**request)
            return
        if staging_console_delivery_enabled():
            # Domainless staging returns the single-use token only in the
            # initiating response. Never write that token to shared logs.
            return
        if is_production():
            raise RuntimeError("AUTH_EMAIL_MODE must be ses in production")
        LOGGER.info("development email to=%s subject=%s body=%s", email, subject, body)


class IdentityService:
    def __init__(self, repository: IdentityRepository, sender: EmailSender | None = None) -> None:
        self.repository = repository
        self.sender = sender or EmailSender()

    def healthcheck(self) -> None:
        self.repository.healthcheck()
        _token_pepper()
        if (
            is_production()
            and os.getenv("AUTH_EMAIL_MODE", "").strip().lower() != "ses"
            and not staging_console_delivery_enabled()
        ):
            raise RuntimeError("production_email_not_configured")

    def signup(
        self, *, email: str, password: str, organization_name: str,
        accepted_terms: bool, display_name: str = "", professional_role: str = "other",
    ) -> tuple[Account, str, bool]:
        display, canonical = canonicalize_email(email)
        validate_password(password, email=canonical)
        organization_name = " ".join(organization_name.split()).strip()
        if not 2 <= len(organization_name) <= 120:
            raise ValueError("Organization name must contain 2 to 120 characters")
        if not accepted_terms:
            raise ValueError("Terms and privacy notice must be accepted")
        display_name = " ".join(display_name.split()).strip()
        if len(display_name) > 100:
            raise ValueError("Name must contain no more than 100 characters")
        if professional_role not in {
            "analyst", "portfolio_manager", "risk", "cio_founder", "other"
        }:
            raise ValueError("Select a valid professional role")
        token = secrets.token_urlsafe(32)
        account = self.repository.create_account(
            email=display,
            canonical_email=canonical,
            password_hash=PASSWORD_HASHER.hash(password),
            organization_name=organization_name,
            display_name=display_name,
            professional_role=professional_role,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            token_hash=hash_token(token),
        )
        delivery_succeeded = True
        try:
            self.sender.send_verification(display, token)
        except Exception:
            # The account transaction already committed. Preserve a recoverable
            # pending account and let the user retry through the generic resend
            # endpoint instead of turning a successful signup into an ambiguous 500.
            delivery_succeeded = False
            LOGGER.exception("verification email delivery failed after account creation")
        return account, token, delivery_succeeded

    def verify_email(
        self, token: str, *, user_agent: str | None, remote_ip: str | None,
    ) -> IssuedSession | None:
        account = self.repository.consume_verification(hash_token(token), utc_now())
        if not account:
            return None
        return self._issue(account, user_agent=user_agent, remote_ip=remote_ip)

    def login(
        self, *, email: str, password: str, user_agent: str | None, remote_ip: str | None,
    ) -> IssuedSession | None:
        try:
            _, canonical = canonicalize_email(email)
        except ValueError:
            PASSWORD_HASHER.hash(password[:PASSWORD_MAX_LENGTH])
            return None
        record = self.repository.login_record(canonical)
        if not record:
            PASSWORD_HASHER.hash(password[:PASSWORD_MAX_LENGTH])
            return None
        now = utc_now()
        locked_until = record.get("locked_until")
        if locked_until and locked_until > now:
            return None
        try:
            valid = PASSWORD_HASHER.verify(record["password_hash"], password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not valid:
            self.repository.record_login_failure(str(record["user_id"]), now)
            return None
        if record["status"] != "active" or not record.get("organization_id"):
            return None
        self.repository.record_login_success(str(record["user_id"]), now)
        account = Account(
            user_id=str(record["user_id"]), email=str(record["email"]), status="active",
            organization_id=str(record["organization_id"]),
            organization_name=str(record["organization_name"]), role=str(record["role"]),
            workspace_id=str(record["workspace_id"]),
            display_name=str(record.get("display_name") or ""),
            professional_role=str(record.get("professional_role") or "other"),
        )
        return self._issue(account, user_agent=user_agent, remote_ip=remote_ip)

    def _issue(
        self, account: Account, *, user_agent: str | None, remote_ip: str | None,
    ) -> IssuedSession:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        identity = self.repository.create_session(
            account=account, token_hash=hash_token(token), csrf_hash=hash_token(csrf_token),
            user_agent_hash=hash_metadata(user_agent), ip_network=ip_prefix(remote_ip),
            now=utc_now(),
        )
        return IssuedSession(identity=identity, token=token, csrf_token=csrf_token)

    def issue_session(
        self, account: Account, *, user_agent: str | None, remote_ip: str | None,
    ) -> IssuedSession:
        """Issue an account session for invitation and organization flows."""
        return self._issue(account, user_agent=user_agent, remote_ip=remote_ip)

    def authenticate_session(self, token: str) -> SessionIdentity | None:
        if not token:
            return None
        return self.repository.get_session(hash_token(token), utc_now())

    def validate_csrf(self, identity: SessionIdentity, token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(identity.csrf_hash, hash_token(token or ""))

    def forgot_password(self, email: str) -> str | None:
        try:
            _, canonical = canonicalize_email(email)
        except ValueError:
            return None
        token = secrets.token_urlsafe(32)
        delivery_email = self.repository.create_password_reset(
            canonical, hash_token(token), utc_now()
        )
        if delivery_email:
            self.sender.send_password_reset(delivery_email, token)
            return token
        return None

    def reset_password(self, token: str, new_password: str) -> bool:
        validate_password(new_password)
        return self.repository.consume_password_reset(
            hash_token(token), PASSWORD_HASHER.hash(new_password), utc_now()
        )

    def resend_verification(self, email: str) -> str | None:
        try:
            _, canonical = canonicalize_email(email)
        except ValueError:
            return None
        token = secrets.token_urlsafe(32)
        delivery_email = self.repository.create_verification(
            canonical, hash_token(token), utc_now()
        )
        if delivery_email:
            self.sender.send_verification(delivery_email, token)
            return token
        return None

    def change_password(
        self, *, email: str, user_id: str, session_id: str,
        current_password: str, new_password: str,
    ) -> bool:
        _, canonical = canonicalize_email(email)
        validate_password(new_password, email=canonical)
        record = self.repository.login_record(canonical)
        if not record or str(record["user_id"]) != user_id:
            return False
        try:
            valid = PASSWORD_HASHER.verify(record["password_hash"], current_password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not valid:
            return False
        return self.repository.change_password(
            user_id, PASSWORD_HASHER.hash(new_password), session_id, utc_now()
        )


_service: IdentityService | None = None
_service_key: str | None = None


def get_identity_service() -> IdentityService:
    global _service, _service_key
    database_url = os.getenv("DATABASE_URL", "").strip()
    key = database_url or "memory"
    if _service is None or _service_key != key:
        repository: IdentityRepository
        repository = (
            PostgresIdentityRepository(database_url)
            if database_url
            else InMemoryIdentityRepository()
        )
        _service = IdentityService(repository)
        _service_key = key
    return _service


def reset_identity_service() -> None:
    global _service, _service_key
    _service = None
    _service_key = None
