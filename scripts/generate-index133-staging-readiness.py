#!/usr/bin/env python3
"""Produce an evidence-backed AWS staging and investor-demo decision."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL = ROOT / "docs/operations/index133-staging-evidence.template.json"
REQUIRED_FILES = [
    ".github/workflows/aws-release.yml",
    "infra/aws/main.tf",
    "infra/aws/variables.tf",
    "infra/aws/bootstrap/control-plane.yaml",
    "infra/aws/bootstrap/edge-certificate.yaml",
    "scripts/configure-github-aws-staging.ps1",
    "scripts/verify-aws-staging-control-plane.py",
    "scripts/verify-github-action-pins.py",
    "docs/operations/AWS_MIGRATION_RUNBOOK.md",
    "docs/operations/index133-staging-evidence.template.json",
]
LIVE_GATES = {
    "prMergedToStaging",
    "stagingBranchProtected",
    "workflowDispatchAvailableOnMain",
    "awsAccountGovernanceApproved",
    "budgetAndAnomalyAlertsActive",
    "stateStorageProtected",
    "route53DelegationVerified",
    "regionalCertificateIssued",
    "edgeCertificateIssued",
    "oidcTrustReviewed",
    "githubEnvironmentProtected",
    "terraformPlanApproved",
    "immutableImagesScannedSigned",
    "databaseMigrationPassed",
    "ecsServicesStable",
    "publicDnsTlsAndHealthPassed",
    "sesVerificationAndEventsPassed",
    "signupToPacketJourneyPassed",
    "crossTenantAdversarialSuitePassed",
    "artifactKmsTenantControlsPassed",
    "alarmsDelivered",
    "currentCostReviewedAgainstBudget",
}
DEMO_EXTRA_GATES = {
    "backupRestoreMeasured",
    "rollbackByDigestExercised",
    "fiveMinuteInvestorDemoRehearsed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-evidence", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/index133-staging-readiness.json")
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--require-demo-ready", action="store_true")
    return parser.parse_args()


def git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def main() -> int:
    options = parse_args()
    external = json.loads(options.external_evidence.read_text(encoding="utf-8"))
    if external.get("schemaVersion") != "index133-staging-evidence.v1":
        raise SystemExit("Unsupported Index133 staging evidence schema.")
    gates = external.get("gates", {})
    missing_gate_names = sorted((LIVE_GATES | DEMO_EXTRA_GATES) - gates.keys())
    invalid_statuses = {
        name: gate.get("status")
        for name, gate in gates.items()
        if gate.get("status") not in {"pending", "passed", "failed", "not_applicable"}
    }
    missing_evidence = sorted(
        name for name, gate in gates.items()
        if gate.get("status") == "passed" and not gate.get("evidence")
    )
    missing_files = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())

    def gates_pass(names: set[str]) -> bool:
        return all(
            gates.get(name, {}).get("status") == "passed"
            and bool(gates.get(name, {}).get("evidence"))
            for name in names
        )

    repository_ready = not missing_files
    staging_live = (
        repository_ready
        and not missing_gate_names
        and not invalid_statuses
        and not missing_evidence
        and gates_pass(LIVE_GATES)
    )
    demo_ready = staging_live and gates_pass(DEMO_EXTRA_GATES)
    report = {
        "schemaVersion": "index133-staging-readiness.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
        "workingTreeDirty": bool(git("status", "--porcelain")),
        "externalEvidenceFile": str(options.external_evidence),
        "repository": {"ready": repository_ready, "missingFiles": missing_files},
        "evidenceErrors": {
            "missingGateNames": missing_gate_names,
            "invalidStatuses": invalid_statuses,
            "passedWithoutEvidence": missing_evidence,
        },
        "pending": sorted(name for name, gate in gates.items() if gate.get("status") == "pending"),
        "failed": sorted(name for name, gate in gates.items() if gate.get("status") == "failed"),
        "awsStagingLive": staging_live,
        "investorDemoReady": demo_ready,
        "decision": "DEMO_READY" if demo_ready else "LIVE" if staging_live else "NO_GO",
        "note": "Repository checks cannot substitute for external AWS, security, product-journey, restore, rollback, cost, or operator evidence.",
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "pendingExternalGates": len(report["pending"]),
        "output": str(options.output),
    }, indent=2))
    if options.require_demo_ready and not demo_ready:
        return 1
    if options.require_live and not staging_live:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
