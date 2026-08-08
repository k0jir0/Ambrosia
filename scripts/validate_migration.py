#!/usr/bin/env python3
"""Compare a read-only Render snapshot with an AWS RDS rehearsal target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
COUNT_TABLES = [
    "reviews", "review_packet", "source_pointers", "audit_events", "workflow_runs",
    "decision_audit", "metric_snapshot", "retrieval_event", "outcome_record",
    "packet_version", "decision_memory_record", "roadmap_plan", "roadmap_decision",
    "roadmap_outcome", "paper_trade", "execution_fill", "relay_run", "durable_job",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate row counts, schema version, tenant keys, and RLS after a migration rehearsal."
    )
    parser.add_argument("--source-url-env", default="RENDER_DATABASE_URL")
    parser.add_argument("--target-url-env", default="AWS_DATABASE_URL")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "migration-validation.json")
    return parser.parse_args()


def connect_from_environment(name: str):
    url = os.getenv(name, "").strip()
    if not url:
        raise RuntimeError(f"{name} is required")
    return psycopg.connect(url, connect_timeout=10, row_factory=dict_row)


def inventory(connection) -> dict:
    server_version = connection.execute("SHOW server_version").fetchone()["server_version"]
    tables = {
        row["table_name"] for row in connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        ).fetchall()
    }
    counts = {}
    for table in COUNT_TABLES:
        if table in tables:
            counts[table] = int(
                connection.execute(
                    sql.SQL("SELECT COUNT(*) AS count FROM {}").format(sql.Identifier(table))
                ).fetchone()["count"]
            )
    extensions = sorted(row["extname"] for row in connection.execute("SELECT extname FROM pg_extension").fetchall())
    migration_rows = []
    if "schema_migration" in tables:
        migration_rows = [dict(row) for row in connection.execute(
            "SELECT version, checksum FROM schema_migration ORDER BY version"
        ).fetchall()]
    return {
        "serverVersion": server_version,
        "extensions": extensions,
        "tables": sorted(tables),
        "counts": counts,
        "migrations": migration_rows,
    }


def target_invariants(connection, tables: set[str]) -> dict:
    tenant_rows = connection.execute(
        """
        SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN information_schema.columns col
          ON col.table_schema = n.nspname AND col.table_name = c.relname
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND col.column_name = 'organization_id'
        ORDER BY c.relname
        """
    ).fetchall()
    null_counts = {}
    for row in tenant_rows:
        table = row["table_name"]
        null_counts[table] = int(
            connection.execute(
                sql.SQL("SELECT COUNT(*) AS count FROM {} WHERE organization_id IS NULL").format(
                    sql.Identifier(table)
                )
            ).fetchone()["count"]
        )
    expected_runtime = connection.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = 'ambrosia_runtime'"
    ).fetchone() is not None
    schema_version = None
    if "schema_migration" in tables:
        row = connection.execute(
            "SELECT MAX(version) AS version FROM schema_migration"
        ).fetchone()
        schema_version = int(row["version"] or 0)
    return {
        "tenantTables": [dict(row) for row in tenant_rows],
        "tenantNullCounts": null_counts,
        "runtimeRoleExists": expected_runtime,
        "schemaMigrationVersion": schema_version,
    }


def main() -> int:
    options = arguments()
    with connect_from_environment(options.source_url_env) as source:
        source.execute("SET TRANSACTION READ ONLY")
        source_inventory = inventory(source)
    with connect_from_environment(options.target_url_env) as target:
        target.execute("SET TRANSACTION READ ONLY")
        target_inventory = inventory(target)
        invariants = target_invariants(target, set(target_inventory["tables"]))

    mismatches = {
        table: {"source": count, "target": target_inventory["counts"].get(table)}
        for table, count in source_inventory["counts"].items()
        if target_inventory["counts"].get(table) != count
    }
    rls_missing = sorted(
        row["table_name"] for row in invariants["tenantTables"] if not row["rls_enabled"]
    )
    null_tenant_rows = {
        table: count for table, count in invariants["tenantNullCounts"].items() if count
    }
    failures = []
    if mismatches:
        failures.append("common-table row counts differ")
    if rls_missing:
        failures.append("tenant tables without RLS")
    if null_tenant_rows:
        failures.append("tenant tables contain NULL organization_id")
    if not invariants["runtimeRoleExists"]:
        failures.append("ambrosia_runtime role missing")
    if (invariants["schemaMigrationVersion"] or 0) < 8:
        failures.append("target schema migration version is below 8")

    snapshot_payload = json.dumps(source_inventory, sort_keys=True, default=str).encode()
    report = {
        "schemaVersion": "migration-validation.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "passed" if not failures else "failed",
        "sourceSnapshotSha256": hashlib.sha256(snapshot_payload).hexdigest(),
        "source": source_inventory,
        "target": target_inventory,
        "targetInvariants": invariants,
        "countMismatches": mismatches,
        "rlsMissing": rls_missing,
        "nullTenantRows": null_tenant_rows,
        "failures": failures,
        "note": "Connection strings and secret values are intentionally excluded.",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(options.output), "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
