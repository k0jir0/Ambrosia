from __future__ import annotations

from pathlib import Path
import sys

import pytest


AMBROSIA_ROOT = Path(__file__).resolve().parents[2]

if str(AMBROSIA_ROOT) not in sys.path:
    sys.path.insert(0, str(AMBROSIA_ROOT))

from services.api.app.models import (  # noqa: E402
    AuditEvent,
    BacktestPlan,
    Claim,
    ConfidenceComponents,
    DecisionPacket,
    FundamentalContext,
    HistoricalAnalogue,
    InterMarketContext,
    MarketSnapshot,
    PortfolioContext,
    RiskMonitor,
    SentimentData,
    SourcePointer,
    TechnicalIndicators,
    ThesisRequest,
    TradeReview,
    TradeabilityQuestion,
    ValidationSpec,
)
from services.api.app.review_engine import generate_review  # noqa: E402


FIXED_TIME = "2026-07-13T12:00:00Z"


def make_thesis_request(
    *,
    ticker: str = "SPY",
    thesis: str | None = None,
    source_pointer: str = "unit-test:source:1",
) -> ThesisRequest:
    return ThesisRequest(
        thesis=thesis or f"{ticker} breadth is improving after a defensive rotation.",
        ticker=ticker,
        asset_class="US equities",
        time_horizon="1-4 weeks",
        intended_expression=f"Long {ticker}",
        source_pointer=source_pointer,
    )


def make_review(
    *,
    ticker: str = "SPY",
    thesis: str | None = None,
    source_pointer: str = "unit-test:source:1",
    trial_count: int = 1,
) -> TradeReview:
    return generate_review(
        make_thesis_request(ticker=ticker, thesis=thesis, source_pointer=source_pointer),
        trial_count=trial_count,
    )


def make_market_snapshot(
    *,
    price: float = 500.0,
    volume: float = 5_000_000,
    source_confidence: str = "fallback",
) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=FIXED_TIME,
        price=price,
        priceChange24h=1.25,
        volume24h=volume,
        dataSource="unit-test-provider",
        dataSourceConfidence=source_confidence,
        freshnessSeconds=0 if source_confidence == "live" else None,
    )


def make_technicals(*, rsi: float | None = 61.0, trend: str = "uptrend") -> TechnicalIndicators:
    return TechnicalIndicators(
        rsi=rsi,
        rsiPeriod=14,
        macdLine=1.1,
        macdSignal=0.7,
        macdHistogram=0.4,
        movingAverage30=495.0,
        movingAverage50=480.0,
        movingAverage200=440.0,
        volatilityRealized=0.18,
        trend=trend,
        updateTime=FIXED_TIME,
        dataQuality="fallback",
        dataMode="fallback",
    )


def make_sentiment(*, score: float = 63.0) -> SentimentData:
    return SentimentData(
        overallScore=score,
        sentiment="bullish" if score >= 60 else "bearish" if score <= 40 else "neutral",
        newsScore=score,
        socialScore=score - 2,
        trendDirection="strengthening" if score >= 58 else "weakening" if score <= 42 else "stable",
        sources=["unit-test"],
        lastUpdated=FIXED_TIME,
        sourceConfidence="demo",
        dataMode="demo",
    )


def make_risk_monitor(*, status: str = "monitoring", active_size: float = 0.05) -> RiskMonitor:
    return RiskMonitor(
        activePositionSize=active_size,
        concentrationRisk="high" if active_size > 0.12 else "medium" if active_size > 0.06 else "low",
        correlationOverlap=["SPY", "QQQ"],
        varAtRisk=round(active_size * 0.8, 4),
        maxDrawdownThreshold=0.12,
        followUpTriggers=["Drawdown threshold breach"],
        status=status,
    )


def make_portfolio_context() -> PortfolioContext:
    return PortfolioContext(
        grossExposure=0.6,
        netExposure=0.35,
        longExposure=0.5,
        shortExposure=0.15,
        concentrationBySector={"Technology": 0.32},
        concentrationByFactor={"Momentum": 0.28},
        relatedPositions=["QQQ"],
        factorOverlap=["Momentum"],
        riskBudgetRemaining=0.18,
        sizingConstraints=["Max 5% NAV"],
    )


def make_confidence_components() -> ConfidenceComponents:
    return ConfidenceComponents(
        evidenceScore=65,
        technicalScore=61,
        sentimentScore=63,
        interMarketScore=55,
        validationScore=70,
        tradeabilityScore=60,
        riskAdjustedScore=58,
        overallConfidence=62,
        blockers=["liquidity_check"],
        sourceProxyPenalties=8,
    )


def make_packet(
    *,
    ticker: str = "SPY",
    confidence: int = 64,
    include_market: bool = True,
    validation_status: str = "specified",
    volume: float = 5_000_000,
    risk_status: str | None = None,
) -> DecisionPacket:
    review = make_review(ticker=ticker, trial_count=2)
    validation = review.validation.model_copy(update={"status": validation_status})
    packet = DecisionPacket(
        id=f"pkt-{ticker.lower()}-unit",
        title=f"{ticker} unit packet",
        thesis=review.thesis,
        ticker=ticker,
        assetClass=review.assetClass,
        timeHorizon=review.timeHorizon,
        intendedExpression=review.intendedExpression,
        status=review.status,
        decisionState=review.decisionState,
        confidence=confidence,
        trialCountImpact=review.trialCountImpact,
        followUpDate=review.followUpDate,
        createdAt=review.createdAt,
        claims=review.claims,
        strongestCritique=review.strongestCritique,
        disconfirmingTest=review.disconfirmingTest,
        historicalAnalogue=review.historicalAnalogue,
        validation=validation,
        tradeability=review.tradeability,
        sources=review.sources,
        audit=review.audit,
        marketSnapshot=make_market_snapshot(volume=volume) if include_market else None,
        technicals=make_technicals() if include_market else None,
        sentiment=make_sentiment() if include_market else None,
        interMarket=InterMarketContext(regimeState="risk_on", spilloverRisk="medium", notes="Unit context"),
        fundamentals=FundamentalContext(growthRate=0.12, qualityScore=72, lastUpdated=FIXED_TIME),
        riskMonitor=make_risk_monitor(status=risk_status) if risk_status else None,
        portfolioContext=make_portfolio_context(),
        confidenceBreakdown=make_confidence_components(),
    )
    return packet


@pytest.fixture
def sample_review() -> TradeReview:
    return make_review()


@pytest.fixture
def sample_packet() -> DecisionPacket:
    return make_packet()


@pytest.fixture
def review_factory():
    return make_review


@pytest.fixture
def packet_factory():
    return make_packet


__all__ = [
    "FIXED_TIME",
    "make_confidence_components",
    "make_market_snapshot",
    "make_packet",
    "make_portfolio_context",
    "make_review",
    "make_risk_monitor",
    "make_sentiment",
    "make_technicals",
    "make_thesis_request",
]
