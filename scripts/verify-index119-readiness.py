#!/usr/bin/env python3
"""Verify repository evidence for the Index119 production standard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "services/api/app/operations.py",
    "services/api/app/resilience.py",
    "services/api/tests/test_index119_operations.py",
    "infra/db/migrations/V0006__production_operations.sql",
    "infra/db/migrations/V0008__identity_tenancy_and_llm_catalog.sql",
    "infra/aws/main.tf",
    "infra/monitoring/index119-alerts.yaml",
    "docs/operations/PRODUCTION_STANDARD.md",
    "docs/operations/INCIDENT_RUNBOOK.md",
    "docs/operations/THREAT_MODEL.md",
    "docs/operations/INDEX119_COMPLETION_LEDGER.md",
    "services/api/tests/test_index119_postgres.py",
    ".github/workflows/security.yml",
]

REQUIRED_MARKERS = {
    "services/api/app/main.py": ["ProductionBoundaryMiddleware", "register_readiness_check"],
    "services/api/app/operations.py": [
        "AMBROSIA_API_KEYS_JSON", "HashChainAuditLog", "DistributedSlidingWindowRateLimiter",
        'router.get("/ready")', 'router.get("/operational/metrics")',
    ],
    "services/hotpath-rs/src/main.rs": [
        "HOTPATH_REQUIRE_APPROVAL", "approval_not_bound_to_order", "replay_detected",
    ],
    "render.yaml": ["healthCheckPath: /ready", "ALLOW_INSECURE_DEV_IDENTITY", "sync: false"],
    "apps/web/next.config.mjs": ["Content-Security-Policy", "Strict-Transport-Security"],
    "infra/db/migrations/V0006__production_operations.sql": [
        "durable_job", "security_audit_event", "execution_replay_guard",
    ],
}


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required artifact: {relative}")
    for relative, markers in REQUIRED_MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing inspected artifact: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                failures.append(f"{relative} missing marker: {marker}")

    schema = json.loads((ROOT / "infra/db/schema-version.json").read_text(encoding="utf-8"))
    if schema.get("dbSchemaVersion") != "v0008":
        failures.append("database schema version is not v0008")

    if failures:
        print("Index119 repository readiness: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Index119 repository readiness: PASS")
    print("External deployment, ownership, penetration-test, restore, and uptime evidence remain environment gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
