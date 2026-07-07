from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.mark.integration
@pytest.mark.critical
@pytest.mark.requires_api
def test_scanner_candidate_can_be_promoted_into_alpha_and_signals(api_client) -> None:
    """Validate Index96 scanner -> alpha promotion flow using live API contracts."""
    scan_response = api_client.post(
        "/scanner/run",
        json={
            "universe": ["AAPL", "MSFT", "SPY"],
            "maxCandidates": 3,
            "minVolume": 1.0,
            "signalFilter": "all",
        },
    )
    assert scan_response.status_code == 200, scan_response.text

    scan_payload = scan_response.json()
    candidates = scan_payload.get("candidates", [])
    assert isinstance(candidates, list)
    assert len(candidates) >= 1
    candidate = candidates[0]

    scanner_run_id = f"scanner-e2e-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    promote_response = api_client.post(
        "/scanner/candidates/promote-alpha",
        json={
            "ticker": candidate["ticker"],
            "signal": candidate["signal"],
            "thesisSuggestion": candidate["thesisSuggestion"],
            "score": candidate["score"],
            "price": candidate["price"],
            "trend": candidate["trend"],
            "rsi": candidate.get("rsi"),
            "volume": candidate["volume24h"],
            "scannerRunId": scanner_run_id,
            "universe": scan_payload.get("universe", [candidate["ticker"]]),
            "horizon": "2-6 weeks",
            "costModel": "10 bps round-trip",
            "benchmark": "SPY",
            "owner": "research",
            "promotedBy": "e2e-suite",
        },
    )
    assert promote_response.status_code == 201, promote_response.text

    promote_payload = promote_response.json()
    assert promote_payload.get("schemaVersion") == "scanner-candidate-promotion.v1"
    assert isinstance(promote_payload.get("hypothesis"), dict)
    assert isinstance(promote_payload.get("signal"), dict)
    assert isinstance(promote_payload.get("link"), dict)

    hypothesis_id = str(promote_payload["link"]["hypothesisId"])
    signal_id = str(promote_payload["link"]["signalId"])
    assert hypothesis_id
    assert signal_id

    signal_snapshot = promote_payload["signal"]
    assert signal_snapshot.get("origin") == "scanner"
    assert signal_snapshot.get("sourceSignal") == candidate["signal"]
    assert signal_snapshot.get("sourceTicker") == candidate["ticker"]

    list_signals_response = api_client.get("/signals")
    assert list_signals_response.status_code == 200, list_signals_response.text
    list_signals_payload = list_signals_response.json()
    assert any(item.get("signalId") == signal_id for item in list_signals_payload)

    list_alpha_response = api_client.get("/alpha/hypotheses")
    assert list_alpha_response.status_code == 200, list_alpha_response.text
    list_alpha_payload = list_alpha_response.json()
    assert any(item.get("hypothesisId") == hypothesis_id for item in list_alpha_payload)

    promotions_response = api_client.get("/scanner/candidates/promotions")
    assert promotions_response.status_code == 200, promotions_response.text
    promotions_payload = promotions_response.json()
    assert any(item.get("signalId") == signal_id for item in promotions_payload)


@pytest.mark.integration
@pytest.mark.critical
@pytest.mark.requires_api
def test_signal_lifecycle_and_review_writeback_flow(api_client) -> None:
    """Exercise validate/promote/link-review/writeback path for newly promoted signals."""
    base_seed = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")

    promote_response = api_client.post(
        "/scanner/candidates/promote-alpha",
        json={
            "ticker": "QQQ",
            "signal": "momentum_up",
            "thesisSuggestion": "QQQ momentum continues with broad tech participation and liquid execution path.",
            "score": 0.81,
            "price": 520.0,
            "trend": "uptrend",
            "rsi": 58.0,
            "volume": 10_000_000,
            "scannerRunId": f"scanner-e2e-{base_seed}",
            "universe": ["QQQ"],
            "horizon": "2-6 weeks",
            "costModel": "10 bps round-trip",
            "benchmark": "SPY",
            "owner": "research",
            "promotedBy": "e2e-suite",
        },
    )
    assert promote_response.status_code == 201, promote_response.text
    promotion = promote_response.json()

    signal_id = str(promotion["link"]["signalId"])
    signal_version = int(promotion["link"].get("signalVersion") or 1)
    hypothesis_id = str(promotion["link"]["hypothesisId"])
    review_id = f"review-e2e-{base_seed}"

    validate_response = api_client.post(
        f"/signals/{signal_id}/validate",
        json={
            "signalVersion": signal_version,
            "runType": "event_driven_backtest",
            "sampleWindows": {
                "train": "2024-01-01/2024-12-31",
                "validation": "2025-01-01/2025-06-30",
                "test": "2025-07-01/2026-01-01",
            },
            "pointInTimeGuaranteed": True,
            "includesCosts": True,
            "includesSlippage": True,
            "includesLiquidity": True,
        },
    )
    assert validate_response.status_code == 200, validate_response.text
    assert validate_response.json().get("status") == "passed"

    promote_signal_response = api_client.post(
        f"/signals/{signal_id}/promote",
        json={
            "signalVersion": signal_version,
            "actor": "e2e-suite",
            "reason": "validated in end-to-end test",
        },
    )
    assert promote_signal_response.status_code == 200, promote_signal_response.text
    assert promote_signal_response.json().get("status") == "active_candidate"

    link_review_response = api_client.post(
        f"/signals/{signal_id}/link-review",
        json={
            "reviewId": review_id,
            "hypothesisId": hypothesis_id,
            "signalVersion": signal_version,
        },
    )
    assert link_review_response.status_code == 201, link_review_response.text

    decision_response = api_client.post(
        f"/signals/{signal_id}/writeback-decision",
        json={
            "reviewId": review_id,
            "signalVersion": signal_version,
            "decisionState": "watch",
            "decisionAction": "HOLD",
            "rationale": "Further evidence required before deployment.",
            "overrideUsed": False,
            "decisionQuality": "D3",
        },
    )
    assert decision_response.status_code == 200, decision_response.text
    decision_payload = decision_response.json()
    assert decision_payload.get("latestDecisionState") == "watch"

    outcome_response = api_client.post(
        f"/signals/{signal_id}/writeback-outcome",
        json={
            "reviewId": review_id,
            "signalVersion": signal_version,
            "outcomeQuality": "validated",
            "lastReviewedAt": datetime.now(UTC).isoformat(),
        },
    )
    assert outcome_response.status_code == 200, outcome_response.text
    outcome_payload = outcome_response.json()
    assert outcome_payload.get("signalId") == signal_id
    assert outcome_payload.get("latestOutcomeQuality") == "validated"

    alpha_context_response = api_client.get(f"/signals/{signal_id}/alpha-context")
    assert alpha_context_response.status_code == 200, alpha_context_response.text
    alpha_context = alpha_context_response.json()
    assert isinstance(alpha_context.get("validationRuns"), list)
    assert isinstance(alpha_context.get("policyEvents"), list)
    assert alpha_context.get("outcomeRollup", {}).get("linkedDecisionCount", 0) >= 1