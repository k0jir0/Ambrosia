#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_EVIDENCE = ROOT / "artifacts" / "release-evidence.json"
ENTERPRISE_EVIDENCE = ROOT / "artifacts" / "enterprise-execution-readiness.json"
ROLLOUT_PACKET = ROOT / "artifacts" / "rollout-evidence-packet.json"


def main() -> int:
    errors: list[str] = []

    if not RELEASE_EVIDENCE.exists():
        errors.append("Missing release evidence artifact")
    if not ENTERPRISE_EVIDENCE.exists():
        errors.append("Missing enterprise execution readiness artifact")

    release = {}
    enterprise = {}
    if RELEASE_EVIDENCE.exists():
        release = json.loads(RELEASE_EVIDENCE.read_text(encoding="utf-8"))
        if release.get("status") != "passed":
            errors.append("release evidence status must be passed")

    if ENTERPRISE_EVIDENCE.exists():
        enterprise = json.loads(ENTERPRISE_EVIDENCE.read_text(encoding="utf-8"))
        checks = enterprise.get("enterpriseGovernance", {}).get("serviceAccount", {}).get("lifecycle", {})
        if not checks:
            errors.append("enterprise evidence missing service account lifecycle checks")

    packet = {
        "status": "failed" if errors else "passed",
        "schemaVersion": "rollout-evidence-packet.v1",
        "releaseEvidence": "artifacts/release-evidence.json",
        "enterpriseEvidence": "artifacts/enterprise-execution-readiness.json",
        "policyChecks": {
            "checksumManifestPresent": RELEASE_EVIDENCE.exists(),
            "serviceAccountLifecyclePresent": bool(enterprise.get("enterpriseGovernance", {}).get("serviceAccount", {}).get("lifecycle")),
        },
        "errors": errors,
    }

    ROLLOUT_PACKET.parent.mkdir(parents=True, exist_ok=True)
    ROLLOUT_PACKET.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("Production evidence verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Production evidence verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
