from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .resilience import resilient_urlopen

ResolutionStatus = Literal[
    "verified", "inactive", "ambiguous", "unsupported", "not_found", "provider_unavailable"
]

RESERVED_TICKERS = {"SAMPLE", "DEMO", "TEST", "TICKER", "SYMBOL", "UNKNOWN", "UNSPECIFIED"}
_SUPPORTED_TYPES = {"EQUITY", "ETF"}
_cache: dict[str, tuple["InstrumentResolution", float]] = {}
_metrics: Counter[str] = Counter()


@dataclass(frozen=True)
class InstrumentResolution:
    requested_symbol: str
    status: ResolutionStatus
    canonical_ticker: str | None = None
    instrument_id: str | None = None
    exchange: str | None = None
    instrument_type: str | None = None
    provider: str = "yahoo-finance"
    verified_at: str | None = None
    reason: str | None = None


def resolve_instrument(raw_symbol: str) -> InstrumentResolution:
    symbol = raw_symbol.strip().upper()
    if symbol in RESERVED_TICKERS or not re.fullmatch(r"[A-Z0-9][A-Z0-9.^/-]{0,14}", symbol):
        result = InstrumentResolution(symbol, "not_found", reason="reserved or invalid ticker")
        _metrics[result.status] += 1
        return result

    now = time.monotonic()
    cached = _cache.get(symbol)
    if cached and now - cached[1] < 300:
        _metrics["cache_hit"] += 1
        return cached[0]

    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5d&interval=1d"
    request = urllib.request.Request(url, headers={"User-Agent": "Ambrosia/1.0"})
    try:
        with resilient_urlopen("yahoo-instrument-reference", request, timeout=3, attempts=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        chart = payload.get("chart", {})
        results = chart.get("result") or []
        if not results:
            result = InstrumentResolution(symbol, "not_found", reason=str(chart.get("error") or "unknown symbol"))
        else:
            meta = results[0].get("meta", {})
            canonical = str(meta.get("symbol") or symbol).upper()
            instrument_type = str(meta.get("instrumentType") or "").upper()
            if instrument_type not in _SUPPORTED_TYPES:
                result = InstrumentResolution(symbol, "unsupported", canonical, instrument_type=instrument_type,
                                              reason="instrument type is outside scanner policy")
            else:
                verified_at = datetime.now(UTC).isoformat()
                result = InstrumentResolution(
                    symbol, "verified", canonical, f"yahoo:{canonical}",
                    str(meta.get("exchangeName") or meta.get("fullExchangeName") or "unknown"),
                    instrument_type, verified_at=verified_at,
                )
    except urllib.error.HTTPError as exc:
        status: ResolutionStatus = "not_found" if exc.code == 404 else "provider_unavailable"
        result = InstrumentResolution(symbol, status, reason=f"provider HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result = InstrumentResolution(symbol, "provider_unavailable", reason=type(exc).__name__)

    _cache[symbol] = (result, now)
    _metrics[result.status] += 1
    return result


def instrument_resolution_metrics() -> dict[str, int]:
    return dict(_metrics)
