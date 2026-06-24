from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DecisionState(str, Enum):
    pursue = "pursue"
    watch = "watch"
    reject = "reject"
    needs_more_data = "needs_more_data"


class ReviewStatus(str, Enum):
    intake = "intake"
    retrieval = "retrieval"
    adversarial_review = "adversarial_review"
    validation = "validation"
    tradeability = "tradeability"
    synthesis = "synthesis"
    decision_recorded = "decision_recorded"


class ThesisRequest(BaseModel):
    thesis: str = Field(min_length=8)
    ticker: str = "Unspecified"
    asset_class: str = "Unspecified"
    time_horizon: str = "Unspecified"
    intended_expression: str = "Expression requires review"
    source_pointer: str = ""


class Claim(BaseModel):
    id: str
    kind: Literal["sourced", "assumption", "inference", "contradiction", "unknown"]
    text: str
    evidence: str | None = None
    confidence: int = Field(ge=0, le=100)


class SourcePointer(BaseModel):
    id: str
    title: str
    sourceType: str
    timestamp: str
    permission: Literal["user_owned", "pointer_only", "public"]
    relevance: float = Field(ge=0, le=1)


class ValidationSpec(BaseModel):
    status: Literal["specified", "refused"]
    hypothesis: str
    nullHypothesis: str
    dataRequirements: list[str]
    protocol: str
    refusalReason: str | None = None


class TradeabilityQuestion(BaseModel):
    topic: str
    question: str
    severity: Literal["low", "medium", "high"]


class AuditEvent(BaseModel):
    id: str
    timestamp: str
    eventType: str
    detail: str


class AuditEventCreate(BaseModel):
    eventType: str = Field(min_length=3)
    detail: str = Field(min_length=3)


class HistoricalAnalogue(BaseModel):
    title: str
    similarity: str
    differences: str
    resolution: str


class MarketSnapshot(BaseModel):
    timestamp: str
    price: float
    priceChange24h: float
    volume24h: float
    marketCap: float | None = None
    dominance: float | None = None
    dataSource: str
    dataSourceConfidence: Literal["live", "fallback", "demo"]


class TechnicalIndicators(BaseModel):
    rsi: float | None = None
    rsiPeriod: int = 14
    macdLine: float | None = None
    macdSignal: float | None = None
    macdHistogram: float | None = None
    movingAverage30: float | None = None
    movingAverage50: float | None = None
    movingAverage200: float | None = None
    volatilityRealized: float | None = None
    trend: Literal["uptrend", "downtrend", "sideways", "unknown"]
    updateTime: str
    dataQuality: Literal["verified", "estimated", "fallback"]


class SentimentData(BaseModel):
    overallScore: float = Field(ge=0, le=100)
    sentiment: Literal["bullish", "neutral", "bearish"]
    newsScore: float | None = None
    socialScore: float | None = None
    trendDirection: Literal["strengthening", "weakening", "stable"]
    sources: list[str]
    lastUpdated: str
    sourceConfidence: Literal["verified", "demo"]


class InterMarketContext(BaseModel):
    correlationWithBenchmark: float | None = None
    correlationWithCommodities: float | None = None
    correlationWithBonds: float | None = None
    correlationWithDollar: float | None = None
    regimeState: Literal["risk_on", "risk_off", "mixed"]
    spilloverRisk: Literal["high", "medium", "low"]
    notes: str


class FundamentalContext(BaseModel):
    earningsYield: float | None = None
    priceToBook: float | None = None
    debtToEquity: float | None = None
    roe: float | None = None
    growthRate: float | None = None
    qualityScore: float | None = None
    lastUpdated: str


class BacktestPlan(BaseModel):
    status: Literal["not_requested", "requested", "eligible", "ineligible", "completed"]
    entryRules: list[str]
    exitRules: list[str]
    assumptions: list[str]
    lookbackPeriod: int
    holdingPeriodDays: int
    riskConstraints: list[str]
    refusalReason: str | None = None


class BacktestResult(BaseModel):
    totalReturn: float | None = None
    sharpeRatio: float | None = None
    maxDrawdown: float | None = None
    winRate: float | None = None
    outOfSampleScore: float | None = None
    samplePeriod: str
    validityScore: Literal["high", "medium", "low", "refused"]
    hygienIssues: list[str]


class RiskMonitor(BaseModel):
    activePositionSize: float
    concentrationRisk: Literal["low", "medium", "high"]
    correlationOverlap: list[str]
    varAtRisk: float | None = None
    maxDrawdownThreshold: float
    followUpTriggers: list[str]
    status: Literal["monitoring", "alert", "safe"]


class PortfolioContext(BaseModel):
    grossExposure: float
    netExposure: float
    longExposure: float
    shortExposure: float
    concentrationBySector: dict[str, float]
    concentrationByFactor: dict[str, float]
    relatedPositions: list[str]
    factorOverlap: list[str]
    riskBudgetRemaining: float
    sizingConstraints: list[str]


class ConfidenceComponents(BaseModel):
    evidenceScore: int = Field(ge=0, le=100)
    technicalScore: int = Field(ge=0, le=100)
    sentimentScore: int = Field(ge=0, le=100)
    interMarketScore: int = Field(ge=0, le=100)
    validationScore: int = Field(ge=0, le=100)
    tradeabilityScore: int = Field(ge=0, le=100)
    riskAdjustedScore: int = Field(ge=0, le=100)
    overallConfidence: int = Field(ge=0, le=100)
    blockers: list[str]
    sourceProxyPenalties: int


class SpecialistAgentOutput(BaseModel):
    role: str
    summary: str
    keyPoints: list[str]
    score: int | None = None
    timestamp: str
    provider: str
    fallbackUsed: bool


class DecisionPacket(BaseModel):
    id: str
    schemaVersion: str = "packet.v1"
    workflowVersion: str = "quant-agent.v1"
    title: str
    thesis: str
    ticker: str
    assetClass: str
    timeHorizon: str
    intendedExpression: str
    status: ReviewStatus
    decisionState: DecisionState | None
    confidence: int = Field(ge=0, le=100)
    trialCountImpact: int
    followUpDate: str
    createdAt: str
    
    # Base review fields
    claims: list[Claim]
    strongestCritique: str
    disconfirmingTest: str
    historicalAnalogue: HistoricalAnalogue
    validation: ValidationSpec
    tradeability: list[TradeabilityQuestion]
    sources: list[SourcePointer]
    audit: list[AuditEvent]
    
    # Quant workflow agent fields
    marketSnapshot: MarketSnapshot | None = None
    technicals: TechnicalIndicators | None = None
    sentiment: SentimentData | None = None
    interMarket: InterMarketContext | None = None
    fundamentals: FundamentalContext | None = None
    backtestPlan: BacktestPlan | None = None
    backtestResult: BacktestResult | None = None
    riskMonitor: RiskMonitor | None = None
    portfolioContext: PortfolioContext | None = None
    confidenceBreakdown: ConfidenceComponents | None = None
    
    # Agent specialist outputs
    agentOutputs: dict[str, SpecialistAgentOutput | None] | None = None
    
    # Coordinator metadata
    coordinatorVersion: str = "coordinator.v1"
    providerInfo: dict | None = None


class TradeReview(BaseModel):
    id: str
    schemaVersion: str = "review.v1"
    workflowVersion: str = "adversarial-review.v1"
    title: str
    thesis: str
    ticker: str
    assetClass: str
    timeHorizon: str
    intendedExpression: str
    status: ReviewStatus
    decisionState: DecisionState | None
    confidence: int = Field(ge=0, le=100)
    trialCountImpact: int
    followUpDate: str
    createdAt: str
    claims: list[Claim]
    strongestCritique: str
    disconfirmingTest: str
    historicalAnalogue: HistoricalAnalogue
    validation: ValidationSpec
    tradeability: list[TradeabilityQuestion]
    sources: list[SourcePointer]
    audit: list[AuditEvent]


class DecisionUpdate(BaseModel):
    decision_state: DecisionState


class OutcomeUpdate(BaseModel):
    outcome: str
    outcome_date: str