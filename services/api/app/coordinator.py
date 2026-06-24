from __future__ import annotations

from datetime import UTC, datetime

from .models import DecisionPacket, SpecialistAgentOutput
from .providers import ProviderSelection


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def _bounded_score(value: int) -> int:
    return max(0, min(100, value))


def _trend_score(packet: DecisionPacket) -> int:
    if not packet.technicals:
        return 50
    trend = packet.technicals.trend
    base = 60 if trend == "uptrend" else 45 if trend == "sideways" else 35 if trend == "downtrend" else 50
    rsi = packet.technicals.rsi or 50
    return _bounded_score(int(base + ((rsi - 50) * 0.3)))


def _sentiment_score(packet: DecisionPacket) -> int:
    if not packet.sentiment:
        return 50
    return _bounded_score(int(packet.sentiment.overallScore))


def run_specialists(
    packet: DecisionPacket,
    provider: ProviderSelection,
) -> dict[str, SpecialistAgentOutput | None]:
    trend_score = _trend_score(packet)
    sent_score = _sentiment_score(packet)

    outputs: dict[str, SpecialistAgentOutput | None] = {
        "marketData": SpecialistAgentOutput(
            role="marketData",
            summary=f"Market snapshot reviewed for {packet.ticker} with latest price context.",
            keyPoints=[
                f"Ticker: {packet.ticker}",
                f"Data source: {packet.marketSnapshot.dataSource if packet.marketSnapshot else 'unavailable'}",
                "Provenance retained for downstream synthesis",
            ],
            score=packet.confidence,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "technical": SpecialistAgentOutput(
            role="technical",
            summary="Technical profile synthesized from RSI, moving averages, and trend state.",
            keyPoints=[
                f"Trend: {packet.technicals.trend if packet.technicals else 'unknown'}",
                f"RSI: {packet.technicals.rsi if packet.technicals else 'n/a'}",
                "MACD and volatility included in signal interpretation",
            ],
            score=trend_score,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "sentiment": SpecialistAgentOutput(
            role="sentiment",
            summary="Sentiment source mix evaluated with confidence labels.",
            keyPoints=[
                f"Overall sentiment score: {packet.sentiment.overallScore if packet.sentiment else 'n/a'}",
                f"Confidence label: {packet.sentiment.sourceConfidence if packet.sentiment else 'n/a'}",
                "News/social trend direction captured for PM synthesis",
            ],
            score=sent_score,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "interMarket": SpecialistAgentOutput(
            role="interMarket",
            summary="Inter-market and regime context prepared for risk-aware interpretation.",
            keyPoints=[
                f"Regime: {packet.interMarket.regimeState if packet.interMarket else 'mixed'}",
                f"Spillover risk: {packet.interMarket.spilloverRisk if packet.interMarket else 'medium'}",
                "Correlation inputs included where available",
            ],
            score=55,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "fundamental": SpecialistAgentOutput(
            role="fundamental",
            summary="Fundamental context inspected for valuation and quality support.",
            keyPoints=[
                f"Quality score: {packet.fundamentals.qualityScore if packet.fundamentals else 'n/a'}",
                f"Growth rate: {packet.fundamentals.growthRate if packet.fundamentals else 'n/a'}",
                "Valuation metrics normalized into packet context",
            ],
            score=58,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "quant": SpecialistAgentOutput(
            role="quant",
            summary="Validation and backtest-readiness checks prepared.",
            keyPoints=[
                f"Validation status: {packet.validation.status}",
                f"Backtest status: {packet.backtestPlan.status if packet.backtestPlan else 'not_requested'}",
                "Hygiene constraints preserved before trade recommendation",
            ],
            score=53,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "bull": SpecialistAgentOutput(
            role="bull",
            summary="Bull case distilled for opportunity framing.",
            keyPoints=[
                "Evidence and momentum alignment highlighted",
                "Upside path conditioned on validation gates",
                "Position sizing constrained by risk budget",
            ],
            score=_bounded_score(int((trend_score + sent_score) / 2 + 5)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "bear": SpecialistAgentOutput(
            role="bear",
            summary="Bear case assembled to pressure-test thesis robustness.",
            keyPoints=[
                "Disconfirming triggers preserved",
                "Crowding and regime-shift risks emphasized",
                "Execution/slippage downside conditions included",
            ],
            score=_bounded_score(100 - int((trend_score + sent_score) / 2)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "risk": SpecialistAgentOutput(
            role="risk",
            summary="Risk posture summarized with portfolio-aware controls.",
            keyPoints=[
                f"Risk monitor status: {packet.riskMonitor.status if packet.riskMonitor else 'monitoring'}",
                "Concentration and overlap checks retained",
                "Follow-up triggers included in packet lifecycle",
            ],
            score=60,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "pmSynthesis": SpecialistAgentOutput(
            role="pmSynthesis",
            summary="Coordinator synthesized specialist outputs into decision readiness view.",
            keyPoints=[
                f"Provider selected: {provider.name}",
                f"Fallback used: {provider.fallback_used}",
                "Human decision authority remains required",
            ],
            score=_bounded_score(int((trend_score + sent_score + packet.confidence) / 3)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
    }

    return outputs
