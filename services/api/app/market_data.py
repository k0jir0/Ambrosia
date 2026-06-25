from __future__ import annotations

import json
import math
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import stdev

from .models import MarketSnapshot, TechnicalIndicators
from .market_providers import fetch_polygon_series, resolve_market_provider

_CACHE_TTL_SECONDS = 60
_series_cache: dict[str, tuple[MarketSeries, float]] = {}


@dataclass
class MarketSeries:
    closes: list[float]
    volumes: list[float]
    source: str
    source_confidence: str


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        return 100.0

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def _moving_average(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _realized_volatility(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] <= 0:
            continue
        returns.append(math.log(values[i] / values[i - 1]))
    if len(returns) < 2:
        return None
    return stdev(returns) * math.sqrt(252)


def _trend(ma30: float | None, ma50: float | None, price: float) -> str:
    if ma30 is None or ma50 is None:
        return "unknown"
    if price > ma30 > ma50:
        return "uptrend"
    if price < ma30 < ma50:
        return "downtrend"
    return "sideways"


def _fetch_yahoo_series(ticker: str) -> MarketSeries:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d"
    request = urllib.request.Request(url, headers={"User-Agent": "Ambrosia/1.0"})

    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise ValueError("No market data in Yahoo response")

    quote = result[0].get("indicators", {}).get("quote", [{}])[0]
    closes_raw = quote.get("close", [])
    volumes_raw = quote.get("volume", [])

    closes = [float(value) for value in closes_raw if value is not None]
    volumes = [float(value) for value in volumes_raw if value is not None]

    if len(closes) < 30 or len(volumes) < 2:
        raise ValueError("Insufficient market history from Yahoo")

    return MarketSeries(
        closes=closes,
        volumes=volumes,
        source="Yahoo Finance",
        source_confidence="live",
    )


def _build_fallback_series(ticker: str) -> MarketSeries:
    random_gen = random.Random(ticker.lower())
    base_price = 80 + random_gen.uniform(20, 220)
    closes = [base_price]
    volumes = [random_gen.uniform(2_000_000, 18_000_000)]

    for _ in range(251):
        drift = random_gen.uniform(-0.028, 0.028)
        next_price = max(1.0, closes[-1] * (1 + drift))
        closes.append(next_price)
        volume_shift = random_gen.uniform(-0.35, 0.35)
        volumes.append(max(100_000, volumes[-1] * (1 + volume_shift)))

    return MarketSeries(
        closes=closes,
        volumes=volumes,
        source="Deterministic fallback",
        source_confidence="fallback",
    )


def get_market_series(ticker: str) -> MarketSeries:
    """Return a MarketSeries, using TTL cache to avoid redundant fetches."""
    now = time.monotonic()
    if ticker in _series_cache:
        cached_series, cached_at = _series_cache[ticker]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return cached_series

    series = _fetch_series_uncached(ticker)
    _series_cache[ticker] = (series, now)
    return series


def _retry_yahoo(ticker: str, max_attempts: int = 2, base_delay: float = 0.3) -> MarketSeries:
    """Call _fetch_yahoo_series with exponential back-off. Raises on exhaustion."""
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(max_attempts):
        try:
            return _fetch_yahoo_series(ticker)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise last_exc


def _fetch_series_uncached(ticker: str) -> MarketSeries:
    """Fetch fresh market data: Polygon (if configured) → Yahoo (with retry) → deterministic fallback."""
    provider = resolve_market_provider()

    if provider.provider_type == "polygon":
        try:
            closes, volumes = fetch_polygon_series(ticker)
            return MarketSeries(
                closes=closes,
                volumes=volumes,
                source="Polygon.io",
                source_confidence="live",
            )
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError):
            pass  # fall through to Yahoo with retry

    try:
        return _retry_yahoo(ticker)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return _build_fallback_series(ticker)


def build_market_snapshot(ticker: str) -> MarketSnapshot:
    series = get_market_series(ticker)
    latest_price = series.closes[-1]
    previous_price = series.closes[-2] if len(series.closes) > 1 else latest_price
    pct_change = 0.0 if previous_price == 0 else ((latest_price - previous_price) / previous_price) * 100

    # freshness: 0 for live (just fetched), None for deterministic fallback
    freshness_seconds = 0 if series.source_confidence == "live" else None

    return MarketSnapshot(
        timestamp=_utc_timestamp(),
        price=round(latest_price, 4),
        priceChange24h=round(pct_change, 4),
        volume24h=round(series.volumes[-1], 2),
        dataSource=series.source,
        dataSourceConfidence=series.source_confidence,
        freshnessSeconds=freshness_seconds,
    )


def build_technicals(ticker: str) -> TechnicalIndicators:
    series = get_market_series(ticker)
    closes = series.closes

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    min_len = min(len(ema12), len(ema26))
    macd_series = [ema12[i] - ema26[i] for i in range(min_len)]
    macd_signal_series = _ema(macd_series, 9)

    macd_line = macd_series[-1] if macd_series else None
    macd_signal = macd_signal_series[-1] if macd_signal_series else None
    macd_histogram = (
        macd_line - macd_signal if macd_line is not None and macd_signal is not None else None
    )

    ma30 = _moving_average(closes, 30)
    ma50 = _moving_average(closes, 50)
    ma200 = _moving_average(closes, 200)
    latest_price = closes[-1]

    return TechnicalIndicators(
        rsi=_rsi(closes, 14),
        rsiPeriod=14,
        macdLine=round(macd_line, 6) if macd_line is not None else None,
        macdSignal=round(macd_signal, 6) if macd_signal is not None else None,
        macdHistogram=round(macd_histogram, 6) if macd_histogram is not None else None,
        movingAverage30=round(ma30, 6) if ma30 is not None else None,
        movingAverage50=round(ma50, 6) if ma50 is not None else None,
        movingAverage200=round(ma200, 6) if ma200 is not None else None,
        volatilityRealized=_realized_volatility(closes),
        trend=_trend(ma30, ma50, latest_price),
        updateTime=_utc_timestamp(),
        dataQuality="verified" if series.source_confidence == "live" else "fallback",
        dataMode=series.source_confidence,
    )
