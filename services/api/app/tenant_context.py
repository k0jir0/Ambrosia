"""Request-scoped tenant context shared by policy and persistence layers."""

from __future__ import annotations

from contextvars import ContextVar, Token

import psycopg

LEGACY_QUARANTINE_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"

_organization_id: ContextVar[str | None] = ContextVar(
    "ambrosia_organization_id", default=None
)


def current_organization_id() -> str | None:
    return _organization_id.get()


def set_organization_id(organization_id: str | None) -> Token:
    return _organization_id.set(organization_id)


def reset_organization_id(token: Token) -> None:
    _organization_id.reset(token)


def apply_tenant_context(connection: psycopg.Connection) -> None:
    """Set the PostgreSQL session variable consumed by defaults and RLS.

    A missing context remains an empty string, which the SQL helper converts to
    NULL. Tenant policies then fail closed instead of selecting every tenant.
    """

    connection.execute(
        "SELECT set_config('app.current_organization_id', %s, false)",
        (current_organization_id() or "",),
    )
