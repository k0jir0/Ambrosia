from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api.app.models import ScannerCandidate, ScannerResult
from services.api.app.store import ReviewStore


@pytest.fixture
def isolated_app(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUIRE_DATABASE", raising=False)

    from services.api.app import main, mobile_api

    store = ReviewStore()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(mobile_api, "store", store)

    return TestClient(main.app), store, main


def test_health_route_returns_service_identity(isolated_app) -> None:
    client, _, _ = isolated_app

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "ambrosia-api"


def test_review_routes_create_list_get_decide_and_record_outcome(isolated_app) -> None:
    client, store, _ = isolated_app

    create = client.post(
        "/reviews",
        json={
            "thesis": "SPY breadth is improving after defensive rotation.",
            "ticker": "SPY",
            "asset_class": "US equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Long SPY",
            "source_pointer": "unit-test:route",
        },
    )
    review = create.json()

    decision = client.patch(f"/reviews/{review['id']}/decision", json={"decision_state": "watch"})
    outcome = client.post(
        f"/reviews/{review['id']}/outcome",
        json={"outcome": "watched successfully", "outcome_date": "2026-07-20"},
    )
    listed = client.get("/reviews")
    fetched = client.get(f"/reviews/{review['id']}")

    assert create.status_code == 200
    assert review["schemaVersion"] == "review.v1"
    assert len(store.list_reviews()) == 1
    assert decision.status_code == 200
    assert decision.json()["decisionState"] == "watch"
    assert outcome.status_code == 200
    assert outcome.json()["audit"][-1]["eventType"] == "outcome.recorded"
    assert listed.json()[0]["id"] == review["id"]
    assert fetched.json()["ticker"] == "SPY"
    assert client.get("/reviews/missing").status_code == 404
    assert client.patch("/reviews/missing/decision", json={"decision_state": "reject"}).status_code == 404


def test_mobile_review_summary_route_uses_same_review_store(isolated_app) -> None:
    client, _, _ = isolated_app
    created = client.post(
        "/reviews",
        json={
            "thesis": "QQQ momentum is firming with a defined invalidation level.",
            "ticker": "QQQ",
            "asset_class": "US equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Long QQQ",
            "source_pointer": "unit-test:mobile",
        },
    ).json()

    response = client.get(f"/mobile/reviews/{created['id']}/summary")
    payload = response.json()

    assert response.status_code == 200
    assert payload["schemaVersion"] == "mobile-review-summary.v1"
    assert payload["review"]["id"] == created["id"]
    assert payload["riskGate"]["requiresServerConfirmation"] is True
    assert payload["signalWriteback"]["canWriteDecision"] is False
    assert payload["nextAction"] == "resolve_hard_blocks_before_pursue"
    assert client.get("/mobile/reviews/missing/summary").status_code == 404


def test_mobile_today_route_summarizes_pending_and_decided_reviews(isolated_app) -> None:
    client, _, _ = isolated_app
    first = client.post(
        "/reviews",
        json={
            "thesis": "AAPL setup needs adversarial review before sizing.",
            "ticker": "AAPL",
            "asset_class": "US equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Long AAPL",
            "source_pointer": "unit-test:aapl",
        },
    ).json()
    client.post(
        "/reviews",
        json={
            "thesis": "MSFT setup needs adversarial review before sizing.",
            "ticker": "MSFT",
            "asset_class": "US equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Long MSFT",
            "source_pointer": "unit-test:msft",
        },
    )
    client.patch(f"/reviews/{first['id']}/decision", json={"decision_state": "watch"})

    today = client.get("/mobile/today").json()

    assert today["schemaVersion"] == "mobile-today.v1"
    assert today["summary"]["pendingReviews"] == 1
    assert today["summary"]["decidedReviews"] == 1
    assert today["freshness"]["reviews"] == "live"


def test_scanner_route_uses_injected_scanner_function(isolated_app, monkeypatch) -> None:
    client, _, main = isolated_app

    def fake_run_scanner(body):
        return ScannerResult(
            candidates=[
                ScannerCandidate(
                    ticker="SPY",
                    signal="momentum_up",
                    thesisSuggestion="SPY unit signal",
                    score=0.9,
                    price=500,
                    trend="uptrend",
                    rsi=61,
                    volume24h=5_000_000,
                    dataSource="unit",
                    dataMode="fallback",
                    scannedAt="2026-07-13T00:00:00Z",
                )
            ],
            scannedAt="2026-07-13T00:00:00Z",
            universe=["SPY"],
            totalScanned=1,
            dataMode="fallback",
        )

    monkeypatch.setattr(main, "run_scanner", fake_run_scanner)

    response = client.post("/scanner/run", json={"universe": ["SPY"], "maxCandidates": 1, "minVolume": 0})

    assert response.status_code == 200
    assert response.json()["candidates"][0]["ticker"] == "SPY"
    assert response.json()["totalScanned"] == 1


def test_scanner_route_honors_runtime_kill_switch(isolated_app, monkeypatch) -> None:
    client, _, _ = isolated_app
    monkeypatch.setenv("MARKET_SCANNER_ENABLED", "false")

    response = client.post("/scanner/run", json={"universe": ["SPY"]})

    assert response.status_code == 503
    assert response.json()["detail"] == "Market Scanner is temporarily unavailable"


def test_scanner_promotion_honors_runtime_safety_gate(isolated_app, monkeypatch) -> None:
    client, _, _ = isolated_app
    monkeypatch.setenv("MARKET_SCANNER_PROMOTION_ENABLED", "false")

    response = client.post(
        "/scanner/candidates/promote-alpha",
        json={
            "ticker": "SPY",
            "signal": "momentum_up",
            "thesisSuggestion": "SPY momentum remains a research hypothesis.",
            "score": 0.8,
            "price": 500,
            "trend": "uptrend",
            "volume": 5_000_000,
        },
    )

    assert response.status_code == 503
    assert "tenant lifecycle storage" in response.json()["detail"]
