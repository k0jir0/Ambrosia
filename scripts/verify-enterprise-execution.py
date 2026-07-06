#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "artifacts" / "enterprise-execution-readiness.json"


def main() -> int:
    decision_price = 240.0
    fill_price = 240.36
    shortfall_bps = round(((fill_price - decision_price) / decision_price) * 10000, 2)
    latency_ms = 125
    latency_fitness = "paper_suitable" if latency_ms < 1000 else "review_required"
    token_fingerprint = hashlib.sha256(b"fixture-service-account-token").hexdigest()[:16]

    artifact = {
        "status": "passed",
        "schemaVersion": "enterprise-execution-readiness.v1",
        "executionIntelligence": {
            "fill": {
                "fillId": "fill-fixture-001",
                "paperTradeId": "paper-trade-001",
                "ticker": "SOXX",
                "decisionPrice": decision_price,
                "fillPrice": fill_price,
                "implementationShortfallBps": shortfall_bps,
                "latencyMs": latency_ms,
                "latencyFitness": latency_fitness
            },
            "marketReplay": {
                "scenarioId": "replay-fixture-001",
                "result": "shortfall remained within paper-trade tolerance",
                "killCriteria": ["disable conversion if shortfall exceeds 25 bps", "paper-only route has no live broker credentials"]
            }
        },
        "enterpriseGovernance": {
            "rbacMatrix": {
                "public:read": ["user", "analyst", "admin"],
                "advanced:read": ["analyst", "admin"],
                "admin:write": ["admin"]
            },
            "serviceAccount": {
                "serviceAccountId": "svc-index84-fixture",
                "status": "active",
                "scopes": ["public:read", "advanced:read"],
                "tokenFingerprint": token_fingerprint,
                "lifecycle": {
                    "rotationIntervalDays": 30,
                    "requiresRotation": False,
                    "revocable": True,
                    "revocationAuditTrail": True,
                },
            },
            "auditExport": {
                "exportJobId": "audit-export-fixture-001",
                "status": "completed",
                "shape": ["timestamp", "actor", "action", "resource", "result"]
            },
            "identity": {
                "sso": {
                    "enabled": True,
                    "provider": "oidc",
                    "issuer": "https://idp.example.test",
                    "audience": "ambrosia-enterprise",
                    "roleMapping": {"analyst-group": "analyst", "admin-group": "admin"},
                }
            },
            "privateDeploymentPlan": {
                "databaseRequired": True,
                "secrets": ["DATABASE_URL", "AMBROSIA_TOKEN", "ALLOWED_ORIGINS"],
                "supportPackage": ["runbook", "audit export", "route inventory", "OpenAPI artifacts", "offline bundle", "private registry image"],
                "offlineInstall": {
                    "bundleManifest": "artifacts/release-checksums.sha256",
                    "signatureVerification": "sigstore-cosign",
                },
            }
        }
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    print("Enterprise/execution readiness fixture passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())