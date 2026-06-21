from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_review_refuses_naive_backtest_language() -> None:
    response = client.post(
        "/reviews",
        json={
            "thesis": "Backtest this BTC miner alpha idea and report a Sharpe ratio",
            "ticker": "BTC miners",
            "asset_class": "Crypto-linked equities",
            "time_horizon": "1-4 weeks",
            "intended_expression": "Long basket",
            "source_pointer": "user note",
        },
    )
    assert response.status_code == 200
    review = response.json()
    assert review["validation"]["status"] == "refused"
    assert review["decisionState"] is None


def test_record_decision() -> None:
    created = client.post(
        "/reviews",
        json={"thesis": "Small-cap overnight liquidity may raise realized volatility", "ticker": "IWM"},
    ).json()
    response = client.patch(f"/reviews/{created['id']}/decision", json={"decision_state": "needs_more_data"})
    assert response.status_code == 200
    assert response.json()["decisionState"] == "needs_more_data"