#!/usr/bin/env python3
"""Produce an honest, machine-readable Index132 release decision."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXTERNAL = ROOT / "docs" / "operations" / "index132-external-evidence.template.json"
REQUIRED_REPOSITORY_FILES = [
    "infra/aws/main.tf",
    "infra/aws/.terraform.lock.hcl",
    "infra/db/migrations/V0008__identity_tenancy_and_llm_catalog.sql",
    "scripts/migrate_database.py",
    "services/api/app/identity.py",
    "services/api/app/tenant_context.py",
    "services/api/app/llm_catalog.py",
    "services/api/app/product_analytics.py",
    "services/api/app/artifact_store.py",
    "services/api/app/tenant_artifacts.py",
    "apps/web/src/app/signup/page.tsx",
    "apps/web/src/app/onboarding/page.tsx",
    "apps/web/src/app/company-proof/page.tsx",
    "apps/web/Dockerfile",
    "services/api/Dockerfile",
    "packages/local-worker/ambrosia_local_worker.py",
    "packages/evals/ollama_disconfirmation_suite.json",
    ".github/workflows/aws-release.yml",
    "docs/operations/AWS_MIGRATION_RUNBOOK.md",
    "docs/operations/RELEASE_CLAIMS_REGISTER.md",
    "docs/operations/INDEX132_IMPLEMENTATION_LEDGER.md",
]


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-evidence", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "index132-readiness.json")
    parser.add_argument("--require-release-ready", action="store_true")
    return parser.parse_args()


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def main() -> int:
    options = args()
    schema = json.loads((ROOT / "infra/db/schema-version.json").read_text(encoding="utf-8"))
    missing_files = [path for path in REQUIRED_REPOSITORY_FILES if not (ROOT / path).is_file()]
    repository_checks = {
        "requiredFiles": {"status": "passed" if not missing_files else "failed", "missing": missing_files},
        "schemaVersion": {
            "status": "passed" if schema.get("dbSchemaVersion", "") >= "v0008" else "failed",
            "actual": schema.get("dbSchemaVersion"),
            "requiredMinimum": "v0008",
        },
        "migrationChain": {
            "status": "passed" if (ROOT / "infra/db/migrations/V0008__identity_tenancy_and_llm_catalog.sql").is_file() else "failed"
        },
    }
    external = json.loads(options.external_evidence.read_text(encoding="utf-8"))
    gates = external.get("gates", {})
    invalid_external = {
        name: value.get("status") for name, value in gates.items()
        if value.get("status") not in {"passed", "failed", "pending", "not_applicable"}
    }
    pending = sorted(name for name, value in gates.items() if value.get("status") == "pending")
    failed = sorted(name for name, value in gates.items() if value.get("status") == "failed")
    missing_evidence = sorted(
        name for name, value in gates.items()
        if value.get("status") == "passed" and not value.get("evidence")
    )
    repository_passed = all(value["status"] == "passed" for value in repository_checks.values())
    release_ready = repository_passed and not (pending or failed or missing_evidence or invalid_external)
    report = {
        "schemaVersion": "index132-readiness.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
        "workingTreeDirty": bool(git("status", "--porcelain")),
        "repositoryChecks": repository_checks,
        "externalEvidenceFile": str(options.external_evidence),
        "externalGateSummary": {
            "pending": pending,
            "failed": failed,
            "passedWithoutEvidence": missing_evidence,
            "invalidStatuses": invalid_external,
        },
        "releaseReady": release_ready,
        "decision": "GO" if release_ready else "NO_GO",
        "note": "Repository implementation is not evidence of a deployed environment, model quality, legal approval, usability, or customer traction.",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "pendingExternalGates": len(pending), "output": str(options.output)}, indent=2))
    return 1 if options.require_release_ready and not release_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
