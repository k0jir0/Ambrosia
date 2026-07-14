from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app

client = TestClient(app)


def test_mobile_today_returns_canonical_summary_without_scanner_run() -> None:
    created = client.post(
        "/reviews",
        json={
            "thesis": "Mobile should surface pending review decisions from canonical API state",
            "ticker": "MOB",
            "asset_class": "US equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Watchlist review",
            "source_pointer": "mobile test",
        },
    )
    assert created.status_code == 200

    response = client.get("/mobile/today")
    assert response.status_code == 200
    payload = response.json()

    assert payload["schemaVersion"] == "mobile-today.v1"
    assert payload["source"] == "api"
    assert payload["summary"]["pendingReviews"] >= 1
    assert payload["scannerCandidates"] == []
    assert payload["scannerStatus"] == "not_requested"
    assert any(item["id"] == created.json()["id"] for item in payload["pendingReviews"])
    assert payload["enterpriseStatus"]["governance"]["humanDecisionAuthority"] is True


def test_mobile_review_summary_exposes_hard_blocks_and_decision_states() -> None:
    created = client.post(
        "/reviews",
        json={
            "thesis": "Backtest this strategy and report the Sharpe ratio before any data is specified",
            "ticker": "QQQ",
            "asset_class": "ETF",
            "time_horizon": "2-6 weeks",
            "intended_expression": "Long ETF",
            "source_pointer": "mobile review summary test",
        },
    )
    assert created.status_code == 200

    response = client.get(f"/mobile/reviews/{created.json()['id']}/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["schemaVersion"] == "mobile-review-summary.v1"
    assert payload["review"]["ticker"] == "QQQ"
    assert "validation_refused" in payload["hardBlocks"]
    assert payload["canPursue"] is False
    assert "needs_more_data" in payload["availableDecisionStates"]
    assert payload["nextAction"] == "resolve_hard_blocks_before_pursue"
    assert payload["historicalAnalogue"]["title"]
    assert payload["runbook"]
    assert any(step["id"] == "validation" for step in payload["runbook"])
    assert payload["providerProvenance"]["provider"] == "ambrosia-fastapi"
    assert payload["riskGate"]["status"] == "blocked"
    assert payload["riskGate"]["requiresServerConfirmation"] is True
    assert payload["signalWriteback"]["requiresLinkedSignal"] is True
    assert payload["reportStatus"]["desktopRoute"].endswith(created.json()["id"])
    assert payload["sources"][0]["title"] == "mobile review summary test"
    assert payload["audit"]


def test_mobile_signal_decision_readiness_reports_missing_review_and_validation() -> None:
    signal_response = client.post(
        "/signals",
        json={
            "signalId": "signal-mobile-contract-test",
            "name": "Mobile Contract Test Signal",
            "formula": "close / close_20d - 1",
            "universe": ["SPY"],
            "horizon": "20d",
            "benchmark": "SPY",
            "costModel": "10 bps round-trip",
        },
    )
    assert signal_response.status_code == 201

    response = client.get("/mobile/signals/signal-mobile-contract-test/decision-readiness")
    assert response.status_code == 200
    payload = response.json()

    assert payload["schemaVersion"] == "mobile-signal-decision-readiness.v1"
    assert payload["signal"]["signalId"] == "signal-mobile-contract-test"
    assert payload["decisionReadiness"] == "blocked_pending_evidence"
    assert "missing_validation_run" in payload["hardBlocks"]
    assert "missing_review_link" in payload["hardBlocks"]
    assert payload["humanDecisionAuthority"] is True
    assert payload["llmInLiveOrderLoop"] is False


def test_mobile_signal_readiness_reflects_validation_and_policy_transition() -> None:
    signal_response = client.post(
        "/signals",
        json={
            "signalId": "signal-mobile-lifecycle-test",
            "name": "Mobile Lifecycle Test Signal",
            "formula": "ret_5d > spy_ret_5d",
            "universe": ["SPY"],
            "horizon": "5d",
            "benchmark": "SPY",
            "costModel": "10 bps round-trip",
        },
    )
    assert signal_response.status_code == 201

    validate_response = client.post(
        "/signals/signal-mobile-lifecycle-test/validate",
        json={
            "runType": "mobile_triage_validation",
            "pointInTimeGuaranteed": True,
            "includesCosts": True,
            "includesSlippage": True,
            "includesLiquidity": True,
        },
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == "passed"

    readiness_after_validation = client.get("/mobile/signals/signal-mobile-lifecycle-test/decision-readiness")
    assert readiness_after_validation.status_code == 200
    validation_payload = readiness_after_validation.json()
    assert "missing_validation_run" not in validation_payload["hardBlocks"]
    assert validation_payload["validationRuns"][0]["status"] == "passed"

    constrain_response = client.post(
        "/signals/signal-mobile-lifecycle-test/constrain",
        json={"actor": "mobile", "reason": "Mobile readiness review found risk constraint."},
    )
    assert constrain_response.status_code == 200
    assert constrain_response.json()["status"] == "constrained"

    readiness_after_constraint = client.get("/mobile/signals/signal-mobile-lifecycle-test/decision-readiness")
    assert readiness_after_constraint.status_code == 200
    constraint_payload = readiness_after_constraint.json()
    assert constraint_payload["signal"]["status"] == "constrained"
    assert constraint_payload["policyEvents"][0]["eventType"] == "signal.constrained"


def test_mobile_contract_covers_signal_review_link_decision_and_outcome_writeback() -> None:
    signal_id = f"signal-mobile-writeback-test-{uuid4().hex[:8]}"
    review_response = client.post(
        "/reviews",
        json={
            "thesis": "Mobile should write reviewed signal decisions back to canonical signal memory",
            "ticker": "AAPL",
            "asset_class": "US equities",
            "time_horizon": "5 days",
            "intended_expression": "Paper signal review",
            "source_pointer": "mobile signal writeback test",
        },
    )
    assert review_response.status_code == 200
    review_id = review_response.json()["id"]

    signal_response = client.post(
        "/signals",
        json={
            "signalId": signal_id,
            "name": "Mobile Writeback Test Signal",
            "formula": "ret_5d > spy_ret_5d",
            "universe": ["AAPL"],
            "horizon": "5d",
            "benchmark": "SPY",
            "costModel": "10 bps round-trip",
        },
    )
    assert signal_response.status_code == 201

    link_response = client.post(
        f"/signals/{signal_id}/link-review",
        json={"reviewId": review_id},
    )
    assert link_response.status_code == 201

    decision_response = client.post(
        f"/signals/{signal_id}/writeback-decision",
        json={
            "reviewId": review_id,
            "decisionState": "watch",
            "decisionAction": "BLOCK",
            "decisionUse": ["mobile_review"],
            "decisionQuality": "D2",
            "approvalState": "mobile_recorded",
            "executionReadiness": "not_executable",
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["latestDecisionState"] == "watch"

    outcome_response = client.post(
        f"/signals/{signal_id}/writeback-outcome",
        json={"reviewId": review_id, "outcomeQuality": "O1_mobile_checkpoint"},
    )
    assert outcome_response.status_code == 200
    assert outcome_response.json()["outcomeCount"] == 1

    readiness_response = client.get(f"/mobile/signals/{signal_id}/decision-readiness")
    assert readiness_response.status_code == 200
    payload = readiness_response.json()
    assert payload["decisionLinks"][0]["reviewDecisionState"] == "watch"
    assert payload["outcomeRollup"]["outcomeCount"] == 1


def test_mobile_enterprise_status_is_read_optimized_and_governed() -> None:
    response = client.get("/mobile/enterprise/status")
    assert response.status_code == 200
    payload = response.json()

    assert payload["schemaVersion"] == "mobile-enterprise-status.v1"
    assert payload["status"] == "ok"
    assert "persistence" in payload
    assert "providers" in payload
    assert payload["governance"]["mobileFinalDecisionsRequireServerConfirmation"] is True
    assert payload["counts"]["reviews"] >= 0
