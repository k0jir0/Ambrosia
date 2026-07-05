#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_PATH = ROOT / "services" / "api"
ARTIFACT_PATH = ROOT / "artifacts" / "index84-literal-completion.json"

sys.path.insert(0, str(API_PATH))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def require_ok(response, label: str) -> dict | list:
    if response.status_code >= 300:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def main() -> int:
    relay = require_ok(
        client.post(
            "/relay/evaluate",
            json={
                "question": "What evidence supports revenue growth?",
                "documents": ["revenue table", "management discussion"],
            },
        ),
        "relay evaluate",
    )
    relay_run = require_ok(client.get(f"/relay/runs/{relay['runId']}"), "relay run get")
    relay_scorecard = require_ok(client.get("/relay/scorecard"), "relay scorecard")
    chat = require_ok(
        client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Summarize the benchmark evidence."}]},
        ),
        "OpenAI-compatible chat",
    )

    feature = require_ok(
        client.post(
            "/features",
            json={"name": "20 day momentum", "ticker": "SOXX", "asOf": "2026-07-01T00:00:00Z", "value": 1.18},
        ),
        "feature upsert",
    )
    signal = require_ok(
        client.post(
            "/signals",
            json={"name": "SOXX momentum", "universe": ["SOXX"], "formula": "close / close_20d - 1"},
        ),
        "signal create",
    )
    alpha_hypothesis = require_ok(
        client.post(
            "/alpha/hypotheses",
            json={
                "title": "Momentum continuation",
                "signalFamily": "momentum",
                "thesis": "Medium horizon trend persistence",
                "universe": ["SOXX"],
                "disconfirmingTests": ["IC below 0.03 for 4 weeks"],
            },
        ),
        "alpha hypothesis create",
    )
    alpha_decay = require_ok(client.get(f"/signals/{signal['signalId']}/alpha-decay"), "alpha decay")
    backtest = require_ok(
        client.post("/backtests/run", json={"signalId": signal["signalId"]}),
        "backtest run",
    )

    paper_trade = require_ok(
        client.post(
            "/paper-trades",
            json={
                "decisionId": "decision-fixture-001",
                "ticker": "SOXX",
                "side": "buy",
                "quantity": 10,
                "intendedPrice": 240,
            },
        ),
        "paper trade create",
    )
    fill = require_ok(
        client.post(
            "/execution/fills",
            json={"paperTradeId": paper_trade["paperTradeId"], "fillPrice": 240.36, "latencyMs": 125},
        ),
        "execution fill ingest",
    )
    replay = require_ok(
        client.post("/execution/market-replay", json={"ticker": "SOXX", "scenario": "spread-widening"}),
        "market replay",
    )
    warm_event = require_ok(
        client.post(
            "/execution/warm-path/events",
            json={"eventType": "fill", "ticker": "SOXX", "latencyMs": 120, "notionalUsd": 15000.0},
        ),
        "warm path event ingest",
    )
    warm_events = require_ok(client.get("/execution/warm-path/events"), "warm path event list")
    warm_path = require_ok(client.get("/execution/warm-path/status"), "warm path status")

    service_account = require_ok(
        client.post(
            "/enterprise/service-accounts",
            json={"name": "index84-ci", "scopes": ["public:read", "advanced:read"]},
        ),
        "service account create",
    )
    rotated_account = require_ok(
        client.post(
            f"/enterprise/service-accounts/{service_account['serviceAccountId']}/rotate",
            json={"rotatedBy": "ci"},
        ),
        "service account rotate",
    )
    revoked_account = require_ok(
        client.post(f"/enterprise/service-accounts/{service_account['serviceAccountId']}/revoke", json={}),
        "service account revoke",
    )
    audit_export = require_ok(
        client.post("/enterprise/audit-exports", json={"requestedBy": "ci", "scope": "all"}),
        "audit export create",
    )
    sso_config = require_ok(
        client.post(
            "/enterprise/sso/config",
            json={
                "provider": "oidc",
                "issuerUrl": "https://idp.example.test",
                "audience": "ambrosia-enterprise",
                "defaultRole": "viewer",
                "roleMappings": {"analyst-group": "analyst", "admin-group": "admin"},
            },
        ),
        "enterprise sso config",
    )
    offline_bundle = require_ok(client.get("/enterprise/deployment-bundles/offline"), "offline bundle manifest")
    security_packet = require_ok(client.get("/enterprise/support/security-packet"), "enterprise security packet")
    enterprise = require_ok(client.get("/enterprise/readiness"), "enterprise readiness")

    errors: list[str] = []
    if relay["schemaVersion"] != "benchmark-trace.v1" or relay_run["runId"] != relay["runId"]:
        errors.append("relay trace/run contract failed")
    if relay_scorecard["calculationVerificationPassRate"] < 1.0:
        errors.append("relay scorecard did not record verifier pass rate")
    if "ambrosiaTrace" not in chat:
        errors.append("OpenAI-compatible chat response missing Ambrosia trace")
    if not feature["pointInTime"]:
        errors.append("feature is not point-in-time labeled")
    if alpha_hypothesis["quality"] != "D3" or alpha_decay["schemaVersion"] != "alpha-decay.v1":
        errors.append("alpha hypothesis/decay contract failed")
    if backtest["status"] != "alpha_candidate" or backtest["metrics"]["implementationShortfallBps"] <= 0:
        errors.append("backtest did not include honest cost/slippage metrics")
    for metric in ["sortinoRatio", "calmarRatio", "informationRatio", "capacityUsdMillions", "factorExposure"]:
        if metric not in backtest["metrics"]:
            errors.append(f"backtest missing extended metric {metric}")
    if "paper_only" not in paper_trade["riskControls"]:
        errors.append("paper trade did not enforce paper-only risk control")
    if fill["latencyFitness"] != "warm_path_ok" or replay["result"] != "accepted":
        errors.append("execution intelligence fixture failed")
    if warm_event["accepted"] is not True or not warm_events:
        errors.append("warm-path event processing contract failed")
    if warm_path["llmInLiveOrderLoop"] is not False:
        errors.append("warm path must exclude LLMs from live order loop")
    if service_account["status"] != "active" or audit_export["status"] != "completed":
        errors.append("enterprise service account/audit export fixture failed")
    if rotated_account.get("lifecycle", {}).get("revocable") is not True:
        errors.append("service account lifecycle rotation contract failed")
    if revoked_account.get("status") != "revoked":
        errors.append("service account revoke contract failed")
    if sso_config.get("enabled") is not True or sso_config.get("provider") != "oidc":
        errors.append("enterprise sso config contract failed")
    if offline_bundle.get("schemaVersion") != "enterprise-offline-bundle.v1":
        errors.append("offline bundle contract failed")
    if security_packet.get("schemaVersion") != "enterprise-security-packet.v1":
        errors.append("enterprise security packet contract failed")
    if not enterprise["packageProvenance"]["checksums"]:
        errors.append("package provenance did not include checksums")

    artifact = {
        "status": "failed" if errors else "passed",
        "schemaVersion": "index84-literal-completion.v1",
        "coveredExpectations": [
            "OpenAI-compatible relay endpoint",
            "benchmark trace, scorecard, evidence, calculation, grounding, abstention contract",
            "point-in-time feature store MVP",
            "signal library MVP",
            "alpha hypothesis object and alpha decay analytics",
            "honest backtest with costs, slippage, benchmark, and disconfirming tests",
            "paper trade conversion and outcome plan",
            "execution fill attribution, market replay, warm-path status, and warm-path event processing",
            "service account token lifecycle (create, rotate, revoke) and audit export",
            "enterprise sso config and offline bundle manifest",
            "enterprise support and security packet",
            "enterprise readiness and package provenance contract",
        ],
        "relayRunId": relay["runId"],
        "featureId": feature["featureId"],
        "signalId": signal["signalId"],
        "backtestId": backtest["backtestId"],
        "paperTradeId": paper_trade["paperTradeId"],
        "fillId": fill["fillId"],
        "serviceAccountId": service_account["serviceAccountId"],
        "auditExportId": audit_export["exportJobId"],
        "errors": errors,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("Index84 literal verifier failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Index84 literal verifier passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
