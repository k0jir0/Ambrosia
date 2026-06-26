from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DecisionState(str, Enum):
    pursue = "pursue"
    watch = "watch"
    reject = "reject"
    needs_more_data = "needs_more_data"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


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
    freshnessSeconds: int | None = None


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
    dataMode: Literal["live", "fallback", "demo"] = "fallback"


class SentimentData(BaseModel):
    overallScore: float = Field(ge=0, le=100)
    sentiment: Literal["bullish", "neutral", "bearish"]
    newsScore: float | None = None
    socialScore: float | None = None
    trendDirection: Literal["strengthening", "weakening", "stable"]
    sources: list[str]
    lastUpdated: str
    sourceConfidence: Literal["verified", "demo"]
    dataMode: Literal["live", "fallback", "demo"] = "demo"


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


class AlertQueueRecord(BaseModel):
    id: str
    source: str
    symbol: str
    message: str
    receivedAt: str
    signatureVerified: bool
    promptInjectionDetected: bool
    payload: dict[str, object]


class AgentRunRequest(BaseModel):
    providerMode: Literal["deterministic", "ollama", "hosted", "hybrid"] = "deterministic"


class BrokerSandboxOrderRequest(BaseModel):
    ticker: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    side: Literal["buy", "sell", "long", "short"]
    price: float | None = None
    source: str = "manual"


class AttributionRequest(BaseModel):
    pnl: float = 0.0
    horizonDays: int = Field(default=20, ge=1, le=365)


class MobileAlertSubscriptionCreate(BaseModel):
    userId: str = "default-user"
    channel: Literal["email", "sms", "push", "webhook", "in_app"] = "in_app"
    target: str = ""
    minSeverity: Literal["info", "warning", "critical"] = "warning"
    enabled: bool = True


class ToolBoundary(BaseModel):
    name: str
    description: str
    mode: Literal["internal", "mcp-compatible"]


class BacktestPrepareRequest(BaseModel):
    lookbackPeriod: int = 252
    holdingPeriodDays: int = 10
    riskConstraints: list[str] = []


class BacktestRunRequest(BaseModel):
    forceRun: bool = False


class RiskEvaluateRequest(BaseModel):
    activePositionSize: float = 0.0
    maxDrawdownThreshold: float = 0.12


class PacketOutcomeUpdate(BaseModel):
    outcome: str
    outcome_date: str
    pnl: float | None = None
    notes: str | None = None


class PortfolioContextUpdate(BaseModel):
    grossExposure: float
    netExposure: float
    longExposure: float
    shortExposure: float
    concentrationBySector: dict[str, float] = {}
    concentrationByFactor: dict[str, float] = {}
    relatedPositions: list[str] = []
    factorOverlap: list[str] = []
    riskBudgetRemaining: float = 0.0
    sizingConstraints: list[str] = []


class ConfidenceDeriveRequest(BaseModel):
    evidenceScore: int | None = None
    technicalScore: int | None = None
    sentimentScore: int | None = None
    interMarketScore: int | None = None
    validationScore: int | None = None
    tradeabilityScore: int | None = None
    blockers: list[str] = []


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=3)
    topK: int = Field(default=5, ge=1, le=20)


class RetrievalHit(BaseModel):
    kind: Literal["prior_review", "packet_source"]
    id: str
    title: str
    snippet: str
    score: float = Field(ge=0, le=1)


class RetrievalResponse(BaseModel):
    packetId: str
    query: str
    results: list[RetrievalHit]


class ScannerRunRequest(BaseModel):
    universe: list[str] | None = None
    maxCandidates: int = Field(default=10, ge=1, le=50)
    minVolume: float = 1_000_000.0
    signalFilter: Literal["momentum", "mean_reversion", "breadth", "all"] = "all"


class ScannerCandidate(BaseModel):
    ticker: str
    signal: Literal["momentum_up", "momentum_down", "mean_reversion_up", "mean_reversion_down", "neutral"]
    thesisSuggestion: str
    score: float = Field(ge=0.0, le=1.0)
    price: float
    trend: str
    rsi: float | None
    volume24h: float
    dataSource: str
    dataMode: Literal["live", "fallback", "demo"]
    scannedAt: str


class ScannerResult(BaseModel):
    candidates: list[ScannerCandidate]
    scannedAt: str
    universe: list[str]
    totalScanned: int
    dataMode: Literal["live", "fallback", "demo"]


class ReportSection(BaseModel):
    title: str
    content: str


class ReportArtifact(BaseModel):
    packetId: str
    ticker: str
    title: str
    createdAt: str
    sections: list[ReportSection]
    dataMode: Literal["live", "fallback", "demo"]
    provenanceLabel: str
    marketDataSource: str | None = None
    marketDataFreshnessSeconds: int | None = None


class JobRecord(BaseModel):
    id: str
    jobType: str
    state: JobState
    queuedAt: str
    startedAt: str | None = None
    completedAt: str | None = None
    inputSummary: str
    result: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Phase 4: Collaboration layer
# ---------------------------------------------------------------------------

class WorkspaceMemberRole(str, Enum):
    owner = "owner"
    analyst = "analyst"
    reviewer = "reviewer"
    viewer = "viewer"


class WorkspaceMember(BaseModel):
    userId: str
    role: WorkspaceMemberRole
    addedAt: str


class WorkspaceRecord(BaseModel):
    id: str
    name: str
    description: str
    createdAt: str
    ownerId: str
    members: list[WorkspaceMember]
    packetIds: list[str]


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=3)
    description: str = ""
    ownerId: str = Field(min_length=1)


class WorkspaceAddPacketRequest(BaseModel):
    packetId: str = Field(min_length=1)


class PacketCommentType(str, Enum):
    general = "general"
    critique = "critique"
    approval_note = "approval_note"
    risk_flag = "risk_flag"


class PacketComment(BaseModel):
    id: str
    packetId: str
    authorId: str
    content: str
    createdAt: str
    commentType: PacketCommentType


class PacketCommentCreate(BaseModel):
    authorId: str = Field(min_length=1)
    content: str = Field(min_length=3)
    commentType: PacketCommentType = PacketCommentType.general


class PacketApprovalDecision(str, Enum):
    approved = "approved"
    rejected = "rejected"
    needs_revision = "needs_revision"


class PacketApproval(BaseModel):
    id: str
    packetId: str
    reviewerId: str
    decision: PacketApprovalDecision
    note: str
    decidedAt: str


class PacketApprovalCreate(BaseModel):
    reviewerId: str = Field(min_length=1)
    decision: PacketApprovalDecision
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 5: Workflow templates (enterprise/marketplace layer)
# ---------------------------------------------------------------------------

class WorkflowTemplateStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class WorkflowTemplateCategory(str, Enum):
    equity_review = "equity_review"
    momentum_scan = "momentum_scan"
    risk_assessment = "risk_assessment"
    custom = "custom"


class WorkflowStep(BaseModel):
    stepId: str
    name: str
    action: str
    params: dict = {}
    humanGate: bool = False


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    version: str
    description: str
    category: WorkflowTemplateCategory
    steps: list[WorkflowStep]
    createdAt: str
    publishedAt: str | None = None
    status: WorkflowTemplateStatus
    authorId: str


class WorkflowTemplateCreate(BaseModel):
    name: str = Field(min_length=3)
    version: str = "1.0.0"
    description: str = ""
    category: WorkflowTemplateCategory = WorkflowTemplateCategory.custom
    steps: list[WorkflowStep] = []
    authorId: str = Field(min_length=1)
