from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    cancelled = "cancelled"


class ReviewStatus(str, Enum):
    intake = "intake"
    retrieval = "retrieval"
    adversarial_review = "adversarial_review"
    validation = "validation"
    tradeability = "tradeability"
    synthesis = "synthesis"
    decision_recorded = "decision_recorded"


class DataMode(str, Enum):
    live = "live"
    fallback = "fallback"
    demo = "demo"


class CoverageStatus(str, Enum):
    full = "full"
    partial = "partial"
    unavailable = "unavailable"


class DisconfirmationStatus(str, Enum):
    not_run = "not_run"
    passed = "pass"
    failed = "fail"
    insufficient_evidence = "insufficient_evidence"
    requires_human_review = "requires_human_review"


class RiskGateStatus(str, Enum):
    not_evaluated = "not_evaluated"
    passed = "pass"
    warning = "warn"
    blocked = "blocked"
    insufficient_data = "insufficient_data"


class IntegrationStage(str, Enum):
    not_started = "not_started"
    evidence_ready = "evidence_ready"
    disconfirmation_pending = "disconfirmation_pending"
    disconfirmation_review = "disconfirmation_review"
    risk_pending = "risk_pending"
    blocked = "blocked"
    human_review = "human_review"
    promotable = "promotable"
    decided = "decided"
    resolved = "resolved"


class ThesisRequest(BaseModel):
    thesis: str = Field(min_length=8)
    ticker: str = "Unspecified"
    asset_class: str = "Unspecified"
    time_horizon: str = "Unspecified"
    intended_expression: str = "Expression requires review"
    source_pointer: str = ""
    subject_type: (
        Literal["listed_instrument", "basket", "macro", "private_asset", "other"] | None
    ) = None
    instrument_id: str | None = None


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
    schemaVersion: str = "specialist-output.v1"
    direction: Literal["supports", "challenges", "mixed", "insufficient"] | None = None
    evidenceStrength: float | None = Field(default=None, ge=0, le=1)
    modelUncertainty: float | None = Field(default=None, ge=0, le=1)
    coverage: float | None = Field(default=None, ge=0, le=1)
    materiality: Literal["low", "medium", "high"] | None = None
    verificationStatus: Literal["unverified", "passed", "repaired", "abstained", "human_review"] = (
        "unverified"
    )
    materialClaims: list["MaterialClaim"] = Field(default_factory=list)
    verificationFindings: list["VerificationFinding"] = Field(default_factory=list)
    rejectedClaims: list["MaterialClaim"] = Field(default_factory=list)
    calculationArtifacts: list["CalculationArtifact"] = Field(default_factory=list)
    missingEvidence: list[str] = Field(default_factory=list)
    falsifiableConditions: list[str] = Field(default_factory=list)
    alternativeHypotheses: list[str] = Field(default_factory=list)
    abstained: bool = False
    abstentionReason: str | None = None
    evidencePackHash: str | None = None
    promptTemplateId: str | None = None
    modelDigest: str | None = None
    finishReason: str | None = None
    truncationDetected: bool = False


class TickerIdentity(BaseModel):
    ticker: str
    canonicalTicker: str
    instrumentId: str
    legalEntityName: str | None = None
    exchangeMic: str | None = None
    cik: str | None = None
    securityType: str = "listed_instrument"
    currency: str | None = None
    shareClass: str | None = None
    effectiveFrom: str | None = None
    effectiveTo: str | None = None
    resolutionProvider: str = "ambrosia-packet"
    resolutionStatus: Literal["verified", "provisional", "ambiguous"] = "provisional"


class EvidenceItemV2(BaseModel):
    evidenceId: str
    evidenceType: str
    subjectInstrumentId: str
    canonicalTicker: str
    sourceName: str
    sourcePointer: str | None = None
    observedAt: str
    retrievedAt: str
    observationCutoff: str
    dataMode: Literal["observed", "derived", "simulated", "user_asserted"]
    freshnessSeconds: int | None = Field(default=None, ge=0)
    content: dict[str, object] = Field(default_factory=dict)
    units: str | None = None
    currency: str | None = None
    period: str | None = None
    permission: str = "public"
    trustBoundary: Literal["trusted_system", "external_data", "user_content"] = "external_data"
    contentHash: str


class ClaimEvidenceRelation(BaseModel):
    evidenceId: str
    relation: Literal["supports", "contradicts", "qualifies", "requires"]


class MaterialClaim(BaseModel):
    claimId: str
    text: str
    claimType: Literal["observation", "inference", "scenario", "opinion"]
    materiality: Literal["low", "medium", "high"] = "medium"
    supportingEvidenceIds: list[str] = Field(default_factory=list)
    contradictingEvidenceIds: list[str] = Field(default_factory=list)
    relations: list[ClaimEvidenceRelation] = Field(default_factory=list)
    premiseClaimIds: list[str] = Field(default_factory=list)
    uncertainty: float = Field(default=0.5, ge=0, le=1)
    falsifier: str | None = None
    calculationId: str | None = None
    admissionStatus: Literal["proposed", "admitted", "repaired", "rejected", "human_review"] = (
        "proposed"
    )


class VerificationFinding(BaseModel):
    claimId: str
    status: Literal[
        "entailed", "contradicted", "insufficient", "nonfactual_opinion", "policy_violation"
    ]
    evidenceIds: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    deterministicChecksPassed: bool = False
    verifier: str = "ambrosia-deterministic"


class SelectiveConfidence(BaseModel):
    direction: Literal["supports", "challenges", "mixed", "insufficient"]
    evidenceStrength: float = Field(ge=0, le=1)
    modelUncertainty: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    materiality: Literal["low", "medium", "high"]


class CalculationIntent(BaseModel):
    calculationId: str
    operation: Literal[
        "add", "subtract", "divide", "percent_change", "percentage_point_change", "margin"
    ]
    inputEvidenceIds: list[str] = Field(min_length=1, max_length=10)
    inputPaths: list[str] = Field(min_length=1, max_length=10)
    units: str | None = None
    scale: str | None = None
    fiscalPeriods: list[str] = Field(default_factory=list)
    roundingDigits: int | None = Field(default=None, ge=0, le=8)


class SpecialistOutputV2(BaseModel):
    schemaVersion: Literal["specialist-output.v2"] = "specialist-output.v2"
    role: str
    instructionReferences: list[str] = Field(default_factory=list)
    materialClaims: list[MaterialClaim] = Field(default_factory=list, max_length=40)
    calculationIntents: list[CalculationIntent] = Field(default_factory=list, max_length=20)
    missingEvidence: list[str] = Field(default_factory=list, max_length=40)
    falsifiableConditions: list[str] = Field(default_factory=list, max_length=40)
    alternativeHypotheses: list[str] = Field(default_factory=list, max_length=40)
    roleConclusion: str
    confidence: SelectiveConfidence
    abstained: bool = False
    abstentionReason: str | None = None


class CalculationArtifact(BaseModel):
    calculationId: str
    operation: str
    inputEvidenceIds: list[str]
    rawValues: list[float]
    units: str | None = None
    scale: str | None = None
    fiscalPeriods: list[str] = Field(default_factory=list)
    formula: str
    result: float
    roundingRule: str = "no_implicit_rounding"
    validationStatus: Literal["passed", "failed", "human_review"]


class MetricLineage(BaseModel):
    function: str
    parameters: dict[str, object] = Field(default_factory=dict)
    inputEnvelopeIds: list[str] = Field(default_factory=list)
    codeVersion: str = "unknown"
    computedAt: str


class ProvenanceMetadata(BaseModel):
    envelopeId: str | None = None
    source: str
    sourceType: str
    timestamp: str
    sourceUrl: str | None = None
    retrievedAt: str | None = None
    asOf: str | None = None
    freshnessSeconds: int | None = Field(default=None, ge=0)
    freshnessSlaSeconds: int | None = Field(default=None, ge=0)
    stale: bool = False
    coverageStatus: CoverageStatus = CoverageStatus.full
    dataMode: DataMode = DataMode.fallback
    license: str | None = None
    feedTier: str | None = None
    pointInTime: bool = False
    confidence: str = "verified"
    notes: str | None = None
    lineage: MetricLineage | None = None


class NumericCheck(BaseModel):
    name: str
    expression: str
    passed: bool | None = None
    observedValue: float | None = None
    threshold: float | None = None
    notes: str | None = None


class DisconfirmationOutcome(BaseModel):
    status: DisconfirmationStatus = DisconfirmationStatus.not_run
    requiresHumanReview: bool = False
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    claimsTested: list[str] = Field(default_factory=list)
    falsifiableConditions: list[str] = Field(default_factory=list)
    alternativeExplanations: list[str] = Field(default_factory=list)
    evidenceReferences: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    missingEvidence: list[str] = Field(default_factory=list)
    numericChecks: list[NumericCheck] = Field(default_factory=list)
    evaluator: str = "ambrosia-deterministic"
    policyVersion: str = "disconfirmation.v1"
    packetVersion: int = Field(default=1, ge=1)
    evaluatedAt: str | None = None
    inputHash: str | None = None


class RiskGateOutcome(BaseModel):
    status: RiskGateStatus = RiskGateStatus.not_evaluated
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    hardBlocks: list[str] = Field(default_factory=list)
    missingInputs: list[str] = Field(default_factory=list)
    evaluator: str = "ambrosia-deterministic"
    policyVersion: str = "risk-policy.v1"
    packetVersion: int = Field(default=1, ge=1)
    evaluatedAt: str | None = None
    inputHash: str | None = None


class DecisionMemoryRecord(BaseModel):
    memoryId: str
    packetId: str
    packetVersion: int = Field(default=1, ge=1)
    recordType: Literal["checkpoint", "resolution"] = "checkpoint"
    outcome: str
    notes: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    createdAt: str
    observedAt: str | None = None
    evidenceReferences: list[str] = Field(default_factory=list)
    packetContentHash: str | None = None
    sequence: int = Field(default=1, ge=1)
    previousHash: str = "0" * 64
    eventHash: str = ""


class PacketAuditChainEvent(BaseModel):
    sequence: int = Field(ge=1)
    packetId: str
    packetVersion: int = Field(ge=1)
    eventType: str
    detail: str
    actor: str = "system"
    createdAt: str
    payloadHash: str
    previousHash: str
    eventHash: str


class PacketWorkflowStatus(BaseModel):
    state: IntegrationStage = IntegrationStage.not_started
    completedStages: list[str] = Field(default_factory=list)
    staleStages: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    nextAction: str = "Attach provenance and run selective integration."
    policyVersion: str = "selective-integration.v1"
    updatedAt: str | None = None


class DecisionPacket(BaseModel):
    id: str
    schemaVersion: str = "packet.v1"
    workflowVersion: str = "quant-agent.v1"
    contractVersion: str = "selective-integration.v1"
    packetVersion: int = Field(default=1, ge=1)
    workflowRunId: str | None = None
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

    # Selective integration fields
    provenance: list[ProvenanceMetadata] = Field(default_factory=list)
    disconfirmationResult: DisconfirmationOutcome | None = None
    riskGateResult: RiskGateOutcome | None = None
    memoryRecords: list[DecisionMemoryRecord] = Field(default_factory=list)
    integrationStatus: PacketWorkflowStatus = Field(default_factory=PacketWorkflowStatus)

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

    @field_validator("provenance", "memoryRecords", mode="before")
    @classmethod
    def normalize_legacy_nullable_lists(cls, value: object) -> object:
        return [] if value is None else value


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


class PacketDecisionUpdate(BaseModel):
    decision_state: DecisionState
    rationale: str = Field(min_length=3)
    actor: str = "human-reviewer"


class MemoryResolutionRequest(BaseModel):
    outcome: str = Field(min_length=2)
    observedAt: str
    score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    evidenceReferences: list[str] = Field(default_factory=list)
    actor: str = "human-reviewer"


class OutcomeUpdate(BaseModel):
    outcome: str
    outcome_date: str


PlanQuality = Literal["P0", "P1", "P2", "P3", "P4"]
DecisionQuality = Literal["D0", "D1", "D2", "D3", "D4", "D5"]
OutcomeQuality = Literal["O0", "O1", "O2", "O3", "O4", "O5"]
RoadmapStatus = Literal["proposed", "scoped", "active", "blocked", "done", "deferred"]


class RoadmapDecisionRecord(BaseModel):
    decision_id: str
    decision_type: str = "implementation"
    quality: DecisionQuality = "D1"
    chosen_path: str
    alternatives_considered: list[str] = Field(default_factory=list)
    rejected_paths: list[str] = Field(default_factory=list)
    user_impact: str = ""
    interface_surface: str = ""
    evidence_links: list[str] = Field(default_factory=list)
    calculation_links: list[str] = Field(default_factory=list)
    confidence: str = ""
    uncertainty: str = ""
    risk_controls: list[str] = Field(default_factory=list)
    human_approver: str = ""
    automation_tier: str = "manual"
    review_date: str


class RoadmapOutcomeRecord(BaseModel):
    outcome_id: str
    quality: OutcomeQuality = "O1"
    actual_result: str
    expected_vs_actual: str = ""
    metric_deltas: list[str] = Field(default_factory=list)
    attribution: str = ""
    cost: str = ""
    latency: str = ""
    data_quality: str = ""
    user_feedback: str = ""
    failure_bucket: str = ""
    follow_up_actions: list[str] = Field(default_factory=list)
    memory_update: str
    next_priority_delta: str = ""


class RoadmapPlanRecord(BaseModel):
    plan_id: str
    title: str
    workstream: str
    owner: str = "TBD"
    quality: PlanQuality
    status: RoadmapStatus
    source_papers: list[str] = Field(default_factory=list)
    external_citations: list[str] = Field(default_factory=list)
    objective: str
    user_value: str
    primary_users: list[str] = Field(default_factory=list)
    core_user_tasks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)
    data_required: list[str] = Field(default_factory=list)
    validation_method: str
    ux_validation_method: str = ""
    decision_gates: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    failure_metrics: list[str] = Field(default_factory=list)
    rollback_plan: str
    security_scope: str = ""
    accessibility_requirements: list[str] = Field(default_factory=list)
    performance_budget: str = ""
    audit_requirements: list[str] = Field(default_factory=list)
    implementation_slice: str = ""
    target_milestone: str = ""
    decisions: list[RoadmapDecisionRecord] = Field(default_factory=list)
    outcomes: list[RoadmapOutcomeRecord] = Field(default_factory=list)


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
    kind: Literal["prior_review", "packet_source", "decision_memory"]
    id: str
    title: str
    snippet: str
    score: float = Field(ge=0, le=1)
    scoreComponents: dict[str, float] | None = None


class RetrievalResponse(BaseModel):
    packetId: str
    query: str
    results: list[RetrievalHit]


class ScannerRunRequest(BaseModel):
    universe: list[str] | None = Field(default=None, max_length=50)
    maxCandidates: int = Field(default=10, ge=1, le=50)
    minVolume: float = Field(default=1_000_000.0, ge=0)
    signalFilter: Literal["momentum", "mean_reversion", "breadth", "all"] = "all"

    @field_validator("universe")
    @classmethod
    def normalize_universe(cls, universe: list[str] | None) -> list[str] | None:
        if universe is None:
            return None
        normalized: list[str] = []
        for raw_ticker in universe:
            ticker = raw_ticker.strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.^/-]{0,14}", ticker):
                raise ValueError(f"Invalid ticker symbol: {raw_ticker!r}")
            if ticker not in normalized:
                normalized.append(ticker)
        return normalized


class ScannerCandidate(BaseModel):
    ticker: str
    signal: Literal[
        "momentum_up", "momentum_down", "mean_reversion_up", "mean_reversion_down", "neutral"
    ]
    thesisSuggestion: str
    score: float = Field(ge=0.0, le=1.0)
    price: float
    trend: str
    rsi: float | None
    volume24h: float
    dataSource: str
    dataMode: Literal["live", "fallback", "demo"]
    scannedAt: str
    instrumentId: str
    canonicalTicker: str
    exchange: str
    verificationProvider: str
    verifiedAt: str
    observedAt: str
    marketDataProvider: str


class ScannerRejectedSymbol(BaseModel):
    ticker: str
    reason: str
    status: Literal[
        "inactive",
        "ambiguous",
        "unsupported",
        "not_found",
        "provider_unavailable",
        "market_data_unavailable",
    ]


class ScannerResult(BaseModel):
    candidates: list[ScannerCandidate]
    scannedAt: str
    universe: list[str]
    totalScanned: int
    dataMode: Literal["live", "fallback", "demo"]
    requestedUniverse: list[str]
    verifiedUniverse: list[str]
    scannedUniverse: list[str]
    rejectedSymbols: list[ScannerRejectedSymbol]


class ReportSection(BaseModel):
    title: str
    content: str
    evidenceMode: Literal[
        "observed", "derived", "simulated", "user_asserted", "mixed", "unavailable"
    ] = "unavailable"
    claimIds: list[str] = Field(default_factory=list)
    citationEvidenceIds: list[str] = Field(default_factory=list)
    verificationStatus: Literal["passed", "partial", "unverified", "unavailable"] = "unverified"


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
    artifactId: str | None = None
    storageStatus: str = "development_not_persisted"
    schemaVersion: str = "ticker-intelligence-report.v1"
    tickerIdentity: TickerIdentity | None = None
    asOf: str | None = None
    knowledgeCutoff: str | None = None
    modelDigest: str | None = None
    promptVersion: str | None = None
    pipelineVersion: str | None = None
    sourceSnapshotHash: str | None = None
    verifiedClaimCoverage: float = Field(default=0, ge=0, le=1)
    unresolvedMaterialClaimCount: int = Field(default=0, ge=0)
    calculationArtifacts: list[CalculationArtifact] = Field(default_factory=list)
    rejectedClaimIds: list[str] = Field(default_factory=list)
    reportValidationStatus: Literal["passed", "partial", "legacy", "failed"] = "legacy"
    operationId: str | None = None
    providerRequested: str | None = None
    providerUsed: str | None = None
    verificationStatus: str | None = None
    traceparent: str | None = None


class ReportDiff(BaseModel):
    packetId: str
    beforePacketVersion: int = Field(ge=1)
    afterPacketVersion: int = Field(ge=1)
    beforeReportHash: str
    afterReportHash: str
    addedClaimIds: list[str] = Field(default_factory=list)
    correctedClaimIds: list[str] = Field(default_factory=list)
    rejectedClaimIds: list[str] = Field(default_factory=list)
    changedSections: list[str] = Field(default_factory=list)
    unchangedSections: list[str] = Field(default_factory=list)
    citationDelta: int = 0
    confidenceDelta: float = 0
    provenance: dict = Field(default_factory=dict)
    artifactId: str | None = None
    storageStatus: str = "development_not_persisted"


class JobRecord(BaseModel):
    id: str
    jobType: str
    state: JobState
    queuedAt: str
    startedAt: str | None = None
    completedAt: str | None = None
    inputSummary: str
    idempotencyKey: str | None = None
    attempt: int = 0
    maxAttempts: int = 3
    timeoutSeconds: int = 300
    cancelRequested: bool = False
    result: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Phase 4: Collaboration layer
# ---------------------------------------------------------------------------


class WorkspaceMemberRole(str, Enum):
    owner = "owner"
    admin = "admin"
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
