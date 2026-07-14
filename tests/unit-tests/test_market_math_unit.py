from __future__ import annotations

from services.api.app.market_data import (
    _build_fallback_series,
    _ema,
    _moving_average,
    _realized_volatility,
    _rsi,
    _trend,
)


def test_moving_average_and_ema_are_deterministic() -> None:
    values = [1, 2, 3, 4, 5]

    assert _moving_average(values, 3) == 4
    assert _moving_average(values, 6) is None
    assert _ema(values, 3) == [1, 1.5, 2.25, 3.125, 4.0625]


def test_rsi_returns_none_for_short_series_and_stays_bounded() -> None:
    assert _rsi([1, 2, 3], period=14) is None
    assert _rsi(list(range(1, 30)), period=14) == 100.0

    mixed = [44, 45, 43, 46, 47, 45, 48, 50, 49, 51, 52, 50, 53, 55, 54, 56, 58]
    rsi = _rsi(mixed, period=14)

    assert rsi is not None
    assert 0 <= rsi <= 100


def test_realized_volatility_requires_enough_positive_returns() -> None:
    assert _realized_volatility([100, 101]) is None
    assert _realized_volatility([100, 101, 99, 102, 103]) is not None


def test_trend_classification_uses_price_and_moving_average_order() -> None:
    assert _trend(105, 100, 110) == "uptrend"
    assert _trend(95, 100, 90) == "downtrend"
    assert _trend(100, 105, 102) == "sideways"
    assert _trend(None, 105, 102) == "unknown"


def test_fallback_series_is_stable_per_ticker_and_distinct_across_tickers() -> None:
    spy_a = _build_fallback_series("SPY")
    spy_b = _build_fallback_series("SPY")
    qqq = _build_fallback_series("QQQ")

    assert spy_a.closes == spy_b.closes
    assert spy_a.volumes == spy_b.volumes
    assert spy_a.closes != qqq.closes
    assert len(spy_a.closes) == 252
    assert spy_a.source_confidence == "fallback"

