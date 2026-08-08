from __future__ import annotations

from datetime import UTC, datetime

from .market_data import build_market_snapshot, build_technicals
from .models import ScannerCandidate, ScannerResult, ScannerRunRequest

_NYSE_DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V",
    "XOM", "WMT", "MA", "PG", "HD", "LLY", "ABBV", "SOXX", "QQQ", "SPY", "IWM",
]

_SIGNAL_FILTER_MAP = {
    "momentum": {"momentum_up", "momentum_down"},
    "mean_reversion": {"mean_reversion_up", "mean_reversion_down"},
    "breadth": {"momentum_up", "mean_reversion_up"},
    "all": {"momentum_up", "momentum_down", "mean_reversion_up", "mean_reversion_down", "neutral"},
}


def _classify_signal(trend: str, rsi: float | None) -> str:
    if rsi is None:
        return "neutral"
    if trend == "uptrend" and 50 < rsi < 70:
        return "momentum_up"
    if trend == "downtrend" and 30 < rsi < 50:
        return "momentum_down"
    if rsi <= 35:
        return "mean_reversion_up"
    if rsi >= 65:
        return "mean_reversion_down"
    return "neutral"


def _score_candidate(signal: str, rsi: float | None, trend: str) -> float:
    base = {"momentum_up": 0.80, "mean_reversion_up": 0.70, "momentum_down": 0.55,
            "mean_reversion_down": 0.45, "neutral": 0.30}.get(signal, 0.30)
    if rsi is not None:
        # boost score for cleaner signals
        if signal == "momentum_up" and rsi < 65:
            base = min(1.0, base + 0.10)
        elif signal == "mean_reversion_up" and rsi < 30:
            base = min(1.0, base + 0.10)
    return round(base, 3)


def _thesis_suggestion(ticker: str, signal: str, trend: str, rsi: float | None) -> str:
    rsi_str = f"{rsi:.0f}" if rsi is not None else "N/A"
    templates = {
        "momentum_up": (
            f"{ticker} is in an {trend} with RSI at {rsi_str}, consistent with a momentum continuation setup. "
            "Consider whether breadth and volume confirm the move before sizing."
        ),
        "momentum_down": (
            f"{ticker} is in a {trend} with RSI at {rsi_str}. "
            "Momentum may persist; evaluate whether a short expression is tractable."
        ),
        "mean_reversion_up": (
            f"{ticker} RSI is at {rsi_str}, signaling a potential oversold mean-reversion long setup. "
            "Confirm that the broader trend and catalyst warrant a contrarian entry."
        ),
        "mean_reversion_down": (
            f"{ticker} RSI is at {rsi_str}, signaling a potential overbought condition. "
            "Evaluate whether thesis fundamentals justify extension or if a fade is warranted."
        ),
        "neutral": (
            f"{ticker} shows no strong directional signal at RSI {rsi_str}. "
            "Hold for a clearer setup or re-evaluate catalyst and timeframe."
        ),
    }
    return templates.get(signal, f"{ticker}: {signal} at RSI {rsi_str}")


def run_scanner(request: ScannerRunRequest) -> ScannerResult:
    universe = [t.upper().strip() for t in request.universe] if request.universe else _NYSE_DEFAULT_UNIVERSE
    allowed_signals = _SIGNAL_FILTER_MAP.get(request.signalFilter, _SIGNAL_FILTER_MAP["all"])
    scanned_at = datetime.now(UTC).isoformat()

    candidates: list[ScannerCandidate] = []
    scanned_tickers: list[str] = []

    for ticker in universe:
        snapshot = build_market_snapshot(ticker)
        technicals = build_technicals(ticker)

        # Volume filter
        if snapshot.volume24h < request.minVolume:
            scanned_tickers.append(ticker)
            continue

        signal = _classify_signal(technicals.trend, technicals.rsi)
        if signal not in allowed_signals:
            scanned_tickers.append(ticker)
            continue

        candidates.append(
            ScannerCandidate(
                ticker=ticker,
                signal=signal,
                thesisSuggestion=_thesis_suggestion(ticker, signal, technicals.trend, technicals.rsi),
                score=_score_candidate(signal, technicals.rsi, technicals.trend),
                price=snapshot.price,
                trend=technicals.trend,
                rsi=technicals.rsi,
                volume24h=snapshot.volume24h,
                dataSource=snapshot.dataSource,
                dataMode=snapshot.dataSourceConfidence,
                scannedAt=scanned_at,
            )
        )
        scanned_tickers.append(ticker)

    candidates.sort(key=lambda c: c.score, reverse=True)
    top_candidates = candidates[: request.maxCandidates]

    overall_mode: str = "fallback"
    if top_candidates and all(candidate.dataMode == "live" for candidate in top_candidates):
        overall_mode = "live"

    return ScannerResult(
        candidates=top_candidates,
        scannedAt=scanned_at,
        universe=scanned_tickers,
        totalScanned=len(scanned_tickers),
        dataMode=overall_mode,
    )
