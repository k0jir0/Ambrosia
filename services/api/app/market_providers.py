from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal


@dataclass
class MarketDataProvider:
    name: str
    provider_type: Literal["polygon", "yahoo", "demo"]
    fallback_chain: list[str] = field(default_factory=list)
    fallback_used: bool = False
    reason: str = ""


def _has_polygon_key() -> bool:
    return bool(os.getenv("POLYGON_API_KEY", "").strip())


def resolve_market_provider() -> MarketDataProvider:
    """Return the highest-priority configured market data provider."""
    if _has_polygon_key():
        return MarketDataProvider(
            name="polygon-io",
            provider_type="polygon",
            fallback_chain=["polygon-io", "yahoo-finance", "deterministic"],
            fallback_used=False,
            reason="POLYGON_API_KEY configured; using licensed NYSE data path",
        )
    return MarketDataProvider(
        name="yahoo-finance",
        provider_type="yahoo",
        fallback_chain=["yahoo-finance", "deterministic"],
        fallback_used=False,
        reason="No licensed key configured; using Yahoo Finance as default",
    )


def market_provider_status() -> dict:
    p = resolve_market_provider()
    return {
        "name": p.name,
        "type": p.provider_type,
        "fallbackChain": p.fallback_chain,
        "fallbackUsed": p.fallback_used,
        "reason": p.reason,
        "polygonConfigured": _has_polygon_key(),
    }


def fetch_polygon_series(ticker: str) -> tuple[list[float], list[float]]:
    """Fetch daily closes and volumes from Polygon.io (licensed NYSE path).

    Returns (closes, volumes).
    Raises ValueError/URLError on failure so callers can fall back.
    """
    api_key = os.getenv("POLYGON_API_KEY", "").strip()
    if not api_key:
        raise ValueError("POLYGON_API_KEY not configured")

    to_date = datetime.now(UTC).date()
    from_date = to_date - timedelta(days=400)  # ~252 trading days within 400 calendar days

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day"
        f"/{from_date}/{to_date}"
        f"?adjusted=true&sort=asc&limit=365&apiKey={api_key}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Ambrosia/1.0"})

    with urllib.request.urlopen(req, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results = payload.get("results") or []
    if len(results) < 30:
        raise ValueError(
            f"Insufficient Polygon data for {ticker}: {len(results)} bars returned"
        )

    closes = [float(bar["c"]) for bar in results if bar.get("c") is not None]
    volumes = [float(bar["v"]) for bar in results if bar.get("v") is not None]

    if len(closes) < 30:
        raise ValueError(f"Not enough close prices from Polygon for {ticker}")

    return closes, volumes
