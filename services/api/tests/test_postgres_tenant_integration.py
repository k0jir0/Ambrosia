from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.identity import EmailSender, IdentityService, PostgresIdentityRepository
from app.tenant_context import apply_tenant_context, reset_organization_id, set_organization_id

RUNTIME_DATABASE_URL = os.getenv("RUNTIME_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUNTIME_DATABASE_URL,
    reason="RUNTIME_DATABASE_URL is only set by the PostgreSQL integration gate",
)


def _account(service: IdentityService, email: str, organization: str):
    account, token, delivered = service.signup(
        email=email,
        password="a database integration passphrase 2026",
        organization_name=organization,
        accepted_terms=True,
        display_name="Integration User",
        professional_role="analyst",
    )
    assert delivered is True
    issued = service.verify_email(token, user_agent="pytest", remote_ip="127.0.0.1")
    assert issued
    return account


def _connection(organization_id: str | None = None):
    connection = psycopg.connect(RUNTIME_DATABASE_URL, row_factory=dict_row)
    token = set_organization_id(organization_id)
    try:
        apply_tenant_context(connection)
    finally:
        reset_organization_id(token)
    return connection


def test_runtime_role_fails_closed_and_row_policies_isolate_organizations(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "integration-test-pepper-value-32-characters")
    service = IdentityService(PostgresIdentityRepository(RUNTIME_DATABASE_URL), EmailSender())
    first = _account(service, f"first-{uuid4().hex}@example.com", "First Tenant")
    second = _account(service, f"second-{uuid4().hex}@example.com", "Second Tenant")

    with _connection() as connection:
        assert connection.execute("SELECT count(*) AS count FROM workspaces").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM reviews").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM product_events").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM artifact_records").fetchone()["count"] == 0

    with _connection(first.organization_id) as connection:
        workspaces = connection.execute(
            "SELECT id, organization_id FROM workspaces ORDER BY created_at"
        ).fetchall()
        assert [str(row["organization_id"]) for row in workspaces] == [first.organization_id]
        connection.execute(
            """
            INSERT INTO reviews (workspace_id, title, thesis, artifact)
            VALUES (%s, 'Tenant A review', 'Only tenant A can see this thesis', '{}'::jsonb)
            """,
            (first.workspace_id,),
        )
        connection.execute(
            """
            INSERT INTO product_events (
              organization_id, user_id, event_type, surface, event_key
            ) VALUES (%s, %s, 'guided_started', 'postgres-integration', %s)
            """,
            (first.organization_id, first.user_id, f"integration-{uuid4().hex}"),
        )
        connection.execute(
            """
            INSERT INTO artifact_records (
              organization_id, artifact_kind, object_reference_hash, storage_key,
              content_hash, content_type, size_bytes, storage_status
            ) VALUES (%s, 'reports', %s, %s, %s, 'application/json', 2, 'durable')
            """,
            (
                first.organization_id,
                "a" * 64,
                f"tenants/{first.organization_id}/reports/{uuid4().hex}/decision.json",
                "b" * 64,
            ),
        )

    with _connection(first.organization_id) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO workspaces (organization_id, name) VALUES (%s, 'Cross tenant')",
                (second.organization_id,),
            )
        connection.rollback()

    with _connection(second.organization_id) as connection:
        assert connection.execute("SELECT count(*) AS count FROM reviews").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM product_events").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM artifact_records").fetchone()["count"] == 0
        workspaces = connection.execute("SELECT organization_id FROM workspaces").fetchall()
        assert [str(row["organization_id"]) for row in workspaces] == [second.organization_id]
