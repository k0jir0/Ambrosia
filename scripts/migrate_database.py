#!/usr/bin/env python3
"""Checksum-verified Ambrosia PostgreSQL bootstrap and migration runner."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "infra" / "db"
MIGRATIONS_DIR = DB_DIR / "migrations"
MIGRATION_PATTERN = re.compile(r"^V(?P<version>\d{4})__[a-z0-9_]+\.sql$")
INCLUDE_PATTERN = re.compile(r"^\\ir\s+(?P<path>.+?)\s*$", re.MULTILINE)
LOCK_KEY = 1_321_2026


def checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def expand_includes(path: Path, seen: set[Path] | None = None) -> str:
    resolved = path.resolve()
    seen = seen or set()
    if resolved in seen:
        raise RuntimeError(f"Recursive SQL include: {resolved}")
    seen.add(resolved)
    content = resolved.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        include = (resolved.parent / match.group("path").strip()).resolve()
        if DB_DIR.resolve() not in include.parents:
            raise RuntimeError(f"SQL include escapes infra/db: {include}")
        return expand_includes(include, seen.copy())

    return INCLUDE_PATTERN.sub(replace, content)


def migrations() -> list[tuple[int, Path, str]]:
    result: list[tuple[int, Path, str]] = []
    for path in sorted(MIGRATIONS_DIR.glob("V*.sql")):
        match = MIGRATION_PATTERN.match(path.name)
        if match:
            content = path.read_text(encoding="utf-8")
            result.append((int(match.group("version")), path, content))
    expected = list(range(1, len(result) + 1))
    actual = [item[0] for item in result]
    if actual != expected:
        raise RuntimeError(f"Migration sequence is not contiguous: {actual}")
    return result


def ensure_ledger(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration (
          version INTEGER PRIMARY KEY,
          filename TEXT NOT NULL UNIQUE,
          checksum CHAR(64) NOT NULL,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def create_runtime_user(connection: psycopg.Connection) -> None:
    username = os.getenv("RUNTIME_DATABASE_USER", "").strip()
    password = os.getenv("RUNTIME_DATABASE_PASSWORD", "")
    if not username and not password:
        return
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", username):
        raise RuntimeError("RUNTIME_DATABASE_USER is invalid")
    if len(password) < 24:
        raise RuntimeError("RUNTIME_DATABASE_PASSWORD must contain at least 24 characters")
    exists = connection.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s", (username,)
    ).fetchone()
    identifier = sql.Identifier(username)
    password_literal = sql.Literal(password)
    if exists:
        connection.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(identifier, password_literal),
        )
    else:
        connection.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN INHERIT PASSWORD {}").format(
                identifier, password_literal
            ),
        )
    connection.execute(
        sql.SQL("GRANT ambrosia_runtime TO {}").format(identifier)
    )
    connection.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(connection.info.dbname), identifier
        )
    )


def mark_migration(connection: psycopg.Connection, version: int, path: Path, content: str) -> None:
    connection.execute(
        """
        INSERT INTO schema_migration (version, filename, checksum)
        VALUES (%s, %s, %s)
        ON CONFLICT (version) DO NOTHING
        """,
        (version, path.name, checksum(content)),
    )


def verify_applied(connection: psycopg.Connection, available: list[tuple[int, Path, str]]) -> set[int]:
    rows = connection.execute(
        "SELECT version, filename, checksum FROM schema_migration ORDER BY version"
    ).fetchall()
    by_version = {version: (path, content) for version, path, content in available}
    applied: set[int] = set()
    for row in rows:
        version = int(row["version"])
        if version not in by_version:
            raise RuntimeError(f"Database has unknown migration version {version}")
        path, content = by_version[version]
        if row["filename"] != path.name or row["checksum"] != checksum(content):
            raise RuntimeError(f"Applied migration V{version:04d} checksum or filename drifted")
        applied.add(version)
    return applied


def execute_migration(connection: psycopg.Connection, content: str) -> None:
    # Migration files may contain PostgreSQL DO blocks and explicit transactions;
    # simple-query mode preserves their multi-statement semantics.
    connection.execute(content, prepare=False)


def run(*, bootstrap_if_empty: bool, check_only: bool) -> None:
    database_url = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    available = migrations()
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            has_schema = connection.execute(
                "SELECT to_regclass('public.reviews') AS relation"
            ).fetchone()["relation"] is not None
            bootstrapped = False
            if not has_schema:
                if check_only or not bootstrap_if_empty:
                    raise RuntimeError("Database is empty; pass --bootstrap-if-empty")
                execute_migration(connection, expand_includes(DB_DIR / "init.sql"))
                bootstrapped = True

            ensure_ledger(connection)
            applied = verify_applied(connection, available)
            if bootstrapped:
                for version, path, content in available:
                    mark_migration(connection, version, path, content)
                applied = {version for version, _, _ in available}
            if not applied and has_schema:
                # Imported Render databases predate the ledger. Their schema is
                # verified by applying the additive/idempotent migrations below;
                # V0001 is a historical marker for init.sql.
                mark_migration(connection, *available[0])
                applied.add(1)

            if not check_only:
                for version, path, content in available:
                    if version in applied:
                        continue
                    execute_migration(connection, content)
                    mark_migration(connection, version, path, content)
                create_runtime_user(connection)

            final_applied = verify_applied(connection, available)
            expected = {version for version, _, _ in available}
            if final_applied != expected:
                raise RuntimeError(
                    f"Database migration set incomplete: expected {sorted(expected)}, "
                    f"found {sorted(final_applied)}"
                )
            print(f"Database schema verified at v{max(expected):04d} ({len(expected)} migrations).")
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-if-empty", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    run(bootstrap_if_empty=args.bootstrap_if_empty, check_only=args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
