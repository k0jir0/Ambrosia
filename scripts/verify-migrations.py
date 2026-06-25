#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "infra" / "db" / "migrations"
SCHEMA_VERSION_PATH = ROOT / "infra" / "db" / "schema-version.json"
INIT_SQL_PATH = ROOT / "infra" / "db" / "init.sql"
MODELS_PATH = ROOT / "services" / "api" / "app" / "models.py"

MIGRATION_PATTERN = re.compile(r"^V(\d{4})__[a-z0-9_]+\.sql$")

REQUIRED_BASELINE_TABLES = [
    "CREATE TABLE IF NOT EXISTS reviews",
    "CREATE TABLE IF NOT EXISTS review_packet",
    "CREATE TABLE IF NOT EXISTS retrieval_event",
    "CREATE TABLE IF NOT EXISTS outcome_record",
]


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def load_schema_version() -> dict:
    if not SCHEMA_VERSION_PATH.exists():
        raise RuntimeError(f"Missing schema version file: {SCHEMA_VERSION_PATH}")
    try:
        data = json.loads(SCHEMA_VERSION_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {SCHEMA_VERSION_PATH}: {exc}") from exc

    required_keys = {"dbSchemaVersion", "reviewArtifactSchema", "packetArtifactSchema"}
    missing = required_keys.difference(data.keys())
    if missing:
        raise RuntimeError(f"schema-version.json missing keys: {', '.join(sorted(missing))}")
    return data


def collect_migrations() -> list[tuple[int, Path]]:
    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(f"Missing migrations directory: {MIGRATIONS_DIR}")

    migrations: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("V*.sql")):
        match = MIGRATION_PATTERN.match(path.name)
        if not match:
            raise RuntimeError(
                "Invalid migration filename pattern "
                f"'{path.name}'. Expected V0001__description.sql"
            )
        migrations.append((int(match.group(1)), path))

    if not migrations:
        raise RuntimeError("No migration files found")

    expected = list(range(1, migrations[-1][0] + 1))
    actual = [version for version, _ in migrations]
    if expected != actual:
        raise RuntimeError(
            "Migration versions must be contiguous starting at 0001. "
            f"Expected {expected}, found {actual}"
        )

    return migrations


def validate_init_sql() -> None:
    if not INIT_SQL_PATH.exists():
        raise RuntimeError(f"Missing init.sql: {INIT_SQL_PATH}")

    content = INIT_SQL_PATH.read_text(encoding="utf-8")
    missing = [table for table in REQUIRED_BASELINE_TABLES if table not in content]
    if missing:
        raise RuntimeError(f"init.sql missing baseline table definitions: {', '.join(missing)}")


def validate_model_schema_contracts(schema_config: dict) -> None:
    if not MODELS_PATH.exists():
        raise RuntimeError(f"Missing models.py: {MODELS_PATH}")

    models_text = MODELS_PATH.read_text(encoding="utf-8")

    review_schema = schema_config["reviewArtifactSchema"]
    packet_schema = schema_config["packetArtifactSchema"]

    if review_schema not in models_text:
        raise RuntimeError(
            "reviewArtifactSchema from schema-version.json "
            f"('{review_schema}') was not found in models.py"
        )

    if packet_schema not in models_text:
        raise RuntimeError(
            "packetArtifactSchema from schema-version.json "
            f"('{packet_schema}') was not found in models.py"
        )


def main() -> int:
    try:
        schema_config = load_schema_version()
        migrations = collect_migrations()
        validate_init_sql()
        validate_model_schema_contracts(schema_config)

        latest_version = migrations[-1][0]
        expected_db_version = f"v{latest_version:04d}"
        configured_db_version = schema_config["dbSchemaVersion"]
        if configured_db_version != expected_db_version:
            return fail(
                "dbSchemaVersion mismatch: "
                f"schema-version.json={configured_db_version}, latest migration={expected_db_version}"
            )

        print("Migration/versioning verification passed.")
        print(f"- Latest migration: {expected_db_version}")
        print(f"- Total migrations: {len(migrations)}")
        print(f"- Review schema contract: {schema_config['reviewArtifactSchema']}")
        print(f"- Packet schema contract: {schema_config['packetArtifactSchema']}")
        return 0
    except RuntimeError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
