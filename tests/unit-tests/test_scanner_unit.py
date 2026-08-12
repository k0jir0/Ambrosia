from __future__ import annotations

import pytest

from services.api.app import scanner
from services.api.app.instrument_registry import InstrumentResolution
from services.api.app.models import MarketSnapshot, ScannerRunRequest, TechnicalIndicators


def _snapshot(price: float, volume: float = 5_000_000) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp="2026-07-13T00:00:00Z",
        price=price,
        priceChange24h=1.2,
        volume24h=volume,
        dataSource="unit-test-provider",
        dataSourceConfidence="live",
    )


def _technicals(rsi: float | None, trend: str) -> TechnicalIndicators:
    return TechnicalIndicators(
        rsi=rsi,
        trend=trend,
        updateTime="2026-07-13T00:00:00Z",
        dataQuality="verified",
        dataMode="live",
    )


@pytest.fixture(autouse=True)
def verified_instruments(monkeypatch) -> None:
    monkeypatch.setattr(
        scanner,
        "resolve_instrument",
        lambda ticker: InstrumentResolution(
            ticker, "verified", ticker, f"test:{ticker}", "TESTX", "EQUITY",
            "unit-test-reference", "2026-07-13T00:00:00Z",
        ),
    )


def test_classify_signal_boundaries() -> None:
    assert scanner._classify_signal("uptrend", 60) == "momentum_up"
    assert scanner._classify_signal("downtrend", 40) == "momentum_down"
    assert scanner._classify_signal("sideways", 28) == "mean_reversion_up"
    assert scanner._classify_signal("uptrend", 72) == "mean_reversion_down"
    assert scanner._classify_signal("unknown", None) == "neutral"


def test_score_candidate_rewards_cleaner_signals() -> None:
    assert scanner._score_candidate("momentum_up", 60, "uptrend") == 0.9
    assert scanner._score_candidate("mean_reversion_up", 28, "sideways") == 0.8
    assert scanner._score_candidate("neutral", 55, "sideways") == 0.3


def test_run_scanner_filters_sorts_and_caps_candidates(monkeypatch) -> None:
    snapshots = {
        "AAPL": _snapshot(210),
        "MSFT": _snapshot(430),
        "TSLA": _snapshot(280),
    }
    technicals = {
        "AAPL": _technicals(60, "uptrend"),
        "MSFT": _technicals(28, "sideways"),
        "TSLA": _technicals(72, "uptrend"),
    }

    monkeypatch.setattr(scanner, "build_market_snapshot", lambda ticker: snapshots[ticker])
    monkeypatch.setattr(scanner, "build_technicals", lambda ticker: technicals[ticker])

    result = scanner.run_scanner(
        ScannerRunRequest(
            universe=["aapl", "msft", "tsla"],
            maxCandidates=2,
            minVolume=0,
            signalFilter="all",
        )
    )

    assert result.universe == ["AAPL", "MSFT", "TSLA"]
    assert result.totalScanned == 3
    assert result.dataMode == "live"
    assert result.requestedUniverse == ["AAPL", "MSFT", "TSLA"]
    assert result.verifiedUniverse == ["AAPL", "MSFT", "TSLA"]
    assert result.rejectedSymbols == []
    assert [candidate.ticker for candidate in result.candidates] == ["AAPL", "MSFT"]
    assert [candidate.score for candidate in result.candidates] == sorted(
        [candidate.score for candidate in result.candidates],
        reverse=True,
    )
    assert all(candidate.thesisSuggestion for candidate in result.candidates)


def test_run_scanner_respects_signal_filter_and_volume_gate(monkeypatch) -> None:
    snapshots = {
        "AAPL": _snapshot(210, volume=5_000_000),
        "MSFT": _snapshot(430, volume=5_000_000),
        "SPY": _snapshot(600, volume=100),
    }
    technicals = {
        "AAPL": _technicals(60, "uptrend"),
        "MSFT": _technicals(28, "sideways"),
        "SPY": _technicals(25, "sideways"),
    }

    monkeypatch.setattr(scanner, "build_market_snapshot", lambda ticker: snapshots[ticker])
    monkeypatch.setattr(scanner, "build_technicals", lambda ticker: technicals[ticker])

    result = scanner.run_scanner(
        ScannerRunRequest(
            universe=["AAPL", "MSFT", "SPY"],
            maxCandidates=10,
            minVolume=1_000_000,
            signalFilter="mean_reversion",
        )
    )

    assert result.totalScanned == 3
    assert [candidate.ticker for candidate in result.candidates] == ["MSFT"]
    assert result.candidates[0].signal == "mean_reversion_up"


def test_scanner_request_normalizes_and_deduplicates_universe() -> None:
    request = ScannerRunRequest(universe=[" aapl ", "AAPL", "brk.b", "BTC/USD"])

    assert request.universe == ["AAPL", "BRK.B", "BTC/USD"]


@pytest.mark.parametrize(
    "payload",
    [
        {"universe": ["AAPL!"]},
        {"universe": [f"TICKER{index}" for index in range(51)]},
        {"minVolume": -1},
    ],
)
def test_scanner_request_rejects_unbounded_or_invalid_input(payload) -> None:
    with pytest.raises(ValueError):
        ScannerRunRequest(**payload)


def test_scanner_rejects_fallback_market_data(monkeypatch) -> None:
    live = _snapshot(210)
    live.dataSourceConfidence = "live"
    fallback = _snapshot(430)
    fallback.dataSourceConfidence = "fallback"
    snapshots = {"AAPL": live, "MSFT": fallback}
    technicals = {
        "AAPL": _technicals(60, "uptrend"),
        "MSFT": _technicals(28, "sideways"),
    }
    monkeypatch.setattr(scanner, "build_market_snapshot", lambda ticker: snapshots[ticker])
    monkeypatch.setattr(scanner, "build_technicals", lambda ticker: technicals[ticker])

    result = scanner.run_scanner(ScannerRunRequest(universe=["AAPL", "MSFT"], minVolume=0))

    assert [candidate.ticker for candidate in result.candidates] == ["AAPL"]
    assert result.dataMode == "live"
    assert result.rejectedSymbols[0].ticker == "MSFT"
    assert result.rejectedSymbols[0].status == "market_data_unavailable"


def test_scanner_rejects_unverified_symbol_before_market_fetch(monkeypatch) -> None:
    monkeypatch.setattr(
        scanner,
        "resolve_instrument",
        lambda ticker: InstrumentResolution(ticker, "not_found", reason="unknown symbol"),
    )
    monkeypatch.setattr(scanner, "build_market_snapshot", lambda ticker: pytest.fail("must not fetch"))

    result = scanner.run_scanner(ScannerRunRequest(universe=["SAMPLE"], minVolume=0))

    assert result.candidates == []
    assert result.scannedUniverse == []
    assert result.rejectedSymbols[0].status == "not_found"

