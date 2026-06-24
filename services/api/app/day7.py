from __future__ import annotations

from .models import (
    ConfidenceComponents,
    ConfidenceDeriveRequest,
    DecisionPacket,
    PortfolioContext,
    PortfolioContextUpdate,
)


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def build_portfolio_context(payload: PortfolioContextUpdate) -> PortfolioContext:
    return PortfolioContext(
        grossExposure=payload.grossExposure,
        netExposure=payload.netExposure,
        longExposure=payload.longExposure,
        shortExposure=payload.shortExposure,
        concentrationBySector=payload.concentrationBySector,
        concentrationByFactor=payload.concentrationByFactor,
        relatedPositions=payload.relatedPositions,
        factorOverlap=payload.factorOverlap,
        riskBudgetRemaining=payload.riskBudgetRemaining,
        sizingConstraints=payload.sizingConstraints,
    )


def derive_confidence(packet: DecisionPacket, payload: ConfidenceDeriveRequest) -> ConfidenceComponents:
    evidence = payload.evidenceScore if payload.evidenceScore is not None else packet.confidence
    technical = (
        payload.technicalScore
        if payload.technicalScore is not None
        else int((packet.technicals.rsi or 50) if packet.technicals else 50)
    )
    sentiment = (
        payload.sentimentScore
        if payload.sentimentScore is not None
        else int(packet.sentiment.overallScore if packet.sentiment else 50)
    )
    inter_market = payload.interMarketScore if payload.interMarketScore is not None else 55
    validation = (
        payload.validationScore
        if payload.validationScore is not None
        else 70 if packet.validation.status == "specified" else 30
    )
    tradeability = payload.tradeabilityScore if payload.tradeabilityScore is not None else 60

    risk_penalty = 0
    if packet.riskMonitor and packet.riskMonitor.status == "alert":
        risk_penalty = 18
    elif packet.riskMonitor and packet.riskMonitor.status == "monitoring":
        risk_penalty = 8

    raw_overall = int(
        (
            evidence * 0.2
            + technical * 0.15
            + sentiment * 0.15
            + inter_market * 0.1
            + validation * 0.2
            + tradeability * 0.2
        )
    )

    overall = _clamp_score(raw_overall - risk_penalty)
    risk_adjusted = _clamp_score(overall - len(payload.blockers) * 3)

    return ConfidenceComponents(
        evidenceScore=_clamp_score(evidence),
        technicalScore=_clamp_score(technical),
        sentimentScore=_clamp_score(sentiment),
        interMarketScore=_clamp_score(inter_market),
        validationScore=_clamp_score(validation),
        tradeabilityScore=_clamp_score(tradeability),
        riskAdjustedScore=_clamp_score(risk_adjusted),
        overallConfidence=overall,
        blockers=payload.blockers,
        sourceProxyPenalties=risk_penalty,
    )
