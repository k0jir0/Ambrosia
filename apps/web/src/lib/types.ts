export type DecisionState = "pursue" | "watch" | "reject" | "needs_more_data";

export type ReviewStatus =
  | "intake"
  | "retrieval"
  | "adversarial_review"
  | "validation"
  | "tradeability"
  | "synthesis"
  | "decision_recorded";

export type ClaimKind = "sourced" | "assumption" | "inference" | "contradiction" | "unknown";

export interface ThesisInput {
  thesis: string;
  ticker: string;
  assetClass: string;
  timeHorizon: string;
  intendedExpression: string;
  sourcePointer: string;
  subjectType?: "listed_instrument" | "basket" | "macro" | "private_asset" | "other";
  instrumentId?: string;
}

export interface Claim {
  id: string;
  kind: ClaimKind;
  text: string;
  evidence?: string;
  confidence: number;
}

export interface SourcePointer {
  id: string;
  title: string;
  sourceType: string;
  timestamp: string;
  permission: "user_owned" | "pointer_only" | "public";
  relevance: number;
}

export interface ValidationSpec {
  status: "specified" | "refused";
  hypothesis: string;
  nullHypothesis: string;
  dataRequirements: string[];
  protocol: string;
  refusalReason?: string;
}

export interface TradeabilityQuestion {
  topic: string;
  question: string;
  severity: "low" | "medium" | "high";
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  eventType: string;
  detail: string;
}

export interface TradeReview {
  id: string;
  schemaVersion: string;
  workflowVersion: string;
  title: string;
  thesis: string;
  ticker: string;
  assetClass: string;
  timeHorizon: string;
  intendedExpression: string;
  status: ReviewStatus;
  decisionState: DecisionState | null;
  confidence: number;
  trialCountImpact: number;
  followUpDate: string;
  createdAt: string;
  claims: Claim[];
  strongestCritique: string;
  disconfirmingTest: string;
  historicalAnalogue: {
    title: string;
    similarity: string;
    differences: string;
    resolution: string;
  };
  validation: ValidationSpec;
  tradeability: TradeabilityQuestion[];
  sources: SourcePointer[];
  audit: AuditEvent[];
}

export interface DashboardMetrics {
  reviewsCreated: number;
  rejectedOrDeferred: number;
  followUpsRecorded: number;
  averageConfidence: number;
  activeTrialCount: number;
}

/**
 * Quant Workflow Agent: Decision Packet Type Definitions
 * These types extend the review artifact to include market data,
 * technicals, sentiment, and multi-agent specialist outputs.
 */

export interface MarketSnapshot {
  timestamp: string;
  price: number;
  priceChange24h: number;
  volume24h: number;
  marketCap?: number;
  dominance?: number;
  dataSource: string;
  dataSourceConfidence: "live" | "fallback" | "demo";
  freshnessSeconds: number | null;
}

export interface TechnicalIndicators {
  rsi: number | null;
  rsiPeriod: number;
  macdLine: number | null;
  macdSignal: number | null;
  macdHistogram: number | null;
  movingAverage30: number | null;
  movingAverage50: number | null;
  movingAverage200: number | null;
  volatilityRealized: number | null;
  trend: "uptrend" | "downtrend" | "sideways" | "unknown";
  updateTime: string;
  dataQuality: "verified" | "estimated" | "fallback";
  dataMode: "live" | "fallback" | "demo";
}

export interface SentimentData {
  overallScore: number;
  sentiment: "bullish" | "neutral" | "bearish";
  newsScore: number | null;
  socialScore: number | null;
  trendDirection: "strengthening" | "weakening" | "stable";
  sources: string[];
  lastUpdated: string;
  sourceConfidence: "verified" | "demo";
  dataMode: "live" | "fallback" | "demo";
}

export interface InterMarketContext {
  correlationWithBenchmark: number | null;
  correlationWithCommodities: number | null;
  correlationWithBonds: number | null;
  correlationWithDollar: number | null;
  regimeState: "risk_on" | "risk_off" | "mixed";
  spilloverRisk: "high" | "medium" | "low";
  notes: string;
}

export interface FundamentalContext {
  earningsYield: number | null;
  priceToBook: number | null;
  debtToEquity: number | null;
  roe: number | null;
  growthRate: number | null;
  qualityScore: number | null;
  lastUpdated: string;
}

export interface BacktestPlan {
  status: "not_requested" | "requested" | "eligible" | "ineligible" | "completed";
  entryRules: string[];
  exitRules: string[];
  assumptions: string[];
  lookbackPeriod: number;
  holdingPeriodDays: number;
  riskConstraints: string[];
  refusalReason?: string;
}

export interface BacktestResult {
  totalReturn: number | null;
  sharpeRatio: number | null;
  maxDrawdown: number | null;
  winRate: number | null;
  outOfSampleScore: number | null;
  samplePeriod: string;
  validityScore: "high" | "medium" | "low" | "refused";
  hygienIssues: string[];
}

export interface RiskMonitor {
  activePositionSize: number;
  concentrationRisk: "low" | "medium" | "high";
  correlationOverlap: string[];
  varAtRisk: number | null;
  maxDrawdownThreshold: number;
  followUpTriggers: string[];
  status: "monitoring" | "alert" | "safe";
}

export interface PortfolioContext {
  grossExposure: number;
  netExposure: number;
  longExposure: number;
  shortExposure: number;
  concentrationBySector: Record<string, number>;
  concentrationByFactor: Record<string, number>;
  relatedPositions: string[];
  factorOverlap: string[];
  riskBudgetRemaining: number;
  sizingConstraints: string[];
}

export interface ConfidenceComponents {
  evidenceScore: number;
  technicalScore: number;
  sentimentScore: number;
  interMarketScore: number;
  validationScore: number;
  tradeabilityScore: number;
  riskAdjustedScore: number;
  overallConfidence: number;
  blockers: string[];
  sourceProxyPenalties: number;
}

export interface SpecialistAgentOutput {
  role: string;
  summary: string;
  keyPoints: string[];
  score: number | null;
  timestamp: string;
  provider: string;
  fallbackUsed: boolean;
  schemaVersion?: string; direction?: "supports"|"challenges"|"mixed"|"insufficient"|null;
  verificationStatus?: "unverified"|"passed"|"repaired"|"abstained"|"human_review";
  materialClaims?: Array<{claimId:string;text:string;claimType:"observation"|"inference"|"scenario"|"opinion";materiality:"low"|"medium"|"high";supportingEvidenceIds:string[];contradictingEvidenceIds:string[];premiseClaimIds:string[];uncertainty:number;falsifier?:string|null;admissionStatus:string}>;
  missingEvidence?: string[]; evidencePackHash?: string|null; modelDigest?: string|null;
}

export type CoverageStatus = "full" | "partial" | "unavailable";
export type DisconfirmationStatus = "not_run" | "pass" | "fail" | "insufficient_evidence" | "requires_human_review";
export type RiskGateStatus = "not_evaluated" | "pass" | "warn" | "blocked" | "insufficient_data";
export type IntegrationStage =
  | "not_started"
  | "evidence_ready"
  | "disconfirmation_pending"
  | "disconfirmation_review"
  | "risk_pending"
  | "blocked"
  | "human_review"
  | "promotable"
  | "decided"
  | "resolved";

export interface MetricLineage {
  function: string;
  parameters: Record<string, unknown>;
  inputEnvelopeIds: string[];
  codeVersion: string;
  computedAt: string;
}

export interface ProvenanceMetadata {
  envelopeId?: string | null;
  source: string;
  sourceType: string;
  timestamp: string;
  sourceUrl?: string | null;
  retrievedAt?: string | null;
  asOf?: string | null;
  freshnessSeconds?: number | null;
  freshnessSlaSeconds?: number | null;
  stale?: boolean;
  coverageStatus?: CoverageStatus;
  dataMode?: "live" | "fallback" | "demo";
  license?: string | null;
  feedTier?: string | null;
  pointInTime?: boolean;
  confidence?: string;
  notes?: string | null;
  lineage?: MetricLineage | null;
}

export interface DisconfirmationOutcome {
  status: DisconfirmationStatus;
  requiresHumanReview: boolean;
  summary: string;
  reasons: string[];
  claimsTested?: string[];
  falsifiableConditions?: string[];
  alternativeExplanations?: string[];
  evidenceReferences?: string[];
  contradictions?: string[];
  missingEvidence?: string[];
  numericChecks?: Array<{
    name: string;
    expression: string;
    passed?: boolean | null;
    observedValue?: number | null;
    threshold?: number | null;
    notes?: string | null;
  }>;
  evaluator?: string;
  policyVersion?: string;
  packetVersion?: number;
  evaluatedAt?: string | null;
  inputHash?: string | null;
}

export interface RiskGateOutcome {
  status: RiskGateStatus;
  reasons: string[];
  warnings?: string[];
  hardBlocks?: string[];
  missingInputs?: string[];
  evaluator?: string;
  policyVersion?: string;
  packetVersion?: number;
  evaluatedAt?: string | null;
  inputHash?: string | null;
}

export interface DecisionMemoryRecord {
  memoryId: string;
  packetId: string;
  packetVersion?: number;
  recordType?: "checkpoint" | "resolution";
  outcome: string;
  notes?: string | null;
  score?: number | null;
  createdAt: string;
  observedAt?: string | null;
  evidenceReferences?: string[];
  packetContentHash?: string | null;
  sequence?: number;
  previousHash?: string;
  eventHash?: string;
}

export interface PacketWorkflowStatus {
  state: IntegrationStage;
  completedStages: string[];
  staleStages: string[];
  blockers: string[];
  nextAction: string;
  policyVersion: string;
  updatedAt?: string | null;
}

export interface DecisionPacket extends TradeReview {
  contractVersion?: string;
  packetVersion?: number;
  workflowRunId?: string | null;
  // Selective integration fields
  provenance?: ProvenanceMetadata[] | null;
  disconfirmationResult?: DisconfirmationOutcome | null;
  riskGateResult?: RiskGateOutcome | null;
  memoryRecords?: DecisionMemoryRecord[] | null;
  integrationStatus?: PacketWorkflowStatus;

  // New quant workflow agent fields
  marketSnapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  interMarket: InterMarketContext | null;
  fundamentals: FundamentalContext | null;
  backtestPlan: BacktestPlan | null;
  backtestResult: BacktestResult | null;
  riskMonitor: RiskMonitor | null;
  portfolioContext: PortfolioContext | null;
  confidenceBreakdown: ConfidenceComponents | null;
  
  // Agent specialist outputs
  agentOutputs: {
    marketData: SpecialistAgentOutput | null;
    technical: SpecialistAgentOutput | null;
    sentiment: SpecialistAgentOutput | null;
    interMarket: SpecialistAgentOutput | null;
    fundamental: SpecialistAgentOutput | null;
    quant: SpecialistAgentOutput | null;
    bull: SpecialistAgentOutput | null;
    bear: SpecialistAgentOutput | null;
    risk: SpecialistAgentOutput | null;
    pmSynthesis: SpecialistAgentOutput | null;
  } | null;
  
  // Coordinator metadata
  coordinatorVersion: string;
  providerInfo: {
    name: string;
    type: "deterministic" | "ollama" | "hosted" | "hybrid";
    fallbackChain: string[];
    fallbackUsed: boolean;
    reason: string;
    pipelineVersion?: string; verifiedRoleCount?: number; humanReviewRoleCount?: number;
    requestedProvider?: string; actualProvider?: string; operationId?: string;
    workerId?: string; modelName?: string; modelDigest?: string; verificationStatus?: string;
    runId?: string; fallbackOperationId?: string; fallbackFromOperationId?: string;
  } | null;
}

export type ProviderMode = "deterministic" | "ollama" | "hosted" | "hybrid";

export interface BacktestPrepareRequest {
  lookbackPeriod: number;
  holdingPeriodDays: number;
  riskConstraints: string[];
}

export interface BacktestRunRequest {
  forceRun: boolean;
}

// ---------------------------------------------------------------------------
// Scanner
// ---------------------------------------------------------------------------

export type ScannerSignal =
  | "momentum_up"
  | "momentum_down"
  | "mean_reversion_up"
  | "mean_reversion_down"
  | "neutral";

export interface ScannerCandidate {
  ticker: string;
  signal: ScannerSignal;
  thesisSuggestion: string;
  score: number;
  price: number;
  trend: string;
  rsi: number | null;
  volume24h: number;
  dataSource: string;
  dataMode: "live" | "fallback" | "demo";
    scannedAt: string;
    instrumentId: string;
    canonicalTicker: string;
    exchange: string;
    verificationProvider: string;
    verifiedAt: string;
    observedAt: string;
    marketDataProvider: string;
}

export interface ScannerResult {
  candidates: ScannerCandidate[];
  scannedAt: string;
  universe: string[];
  totalScanned: number;
    dataMode: "live" | "fallback" | "demo";
    requestedUniverse: string[];
    verifiedUniverse: string[];
    scannedUniverse: string[];
    rejectedSymbols: Array<{ ticker: string; reason: string; status: string }>;
}

export interface ScannerRunRequest {
  universe?: string[];
  maxCandidates?: number;
  minVolume?: number;
  signalFilter?: "momentum" | "mean_reversion" | "breadth" | "all";
}

export type ScannerPromotionStatus =
  | "alpha_created"
  | "signal_linked"
  | "review_linked"
  | "hypothesis"
  | "validation_pending"
  | "validation_passed"
  | "active_candidate"
  | "constrained"
  | "retired";

export interface ScannerCandidatePromoteRequest {
  ticker: string;
  signal: string;
  thesisSuggestion: string;
  score: number;
  price: number;
  trend: string;
  rsi: number | null;
  volume: number;
  scannerRunId?: string;
  universe: string[];
  horizon: string;
  costModel: string;
  benchmark: string;
  owner: string;
  promotedBy: string;
}

export interface ScannerCandidatePromotion {
  promotionId: string;
  candidateKey: string;
  ticker: string;
  signal: string;
  scannerRunId: string;
  hypothesisId?: string;
  signalId?: string;
  signalVersion?: number;
  promotedAt: string;
  promotedBy: string;
  status: ScannerPromotionStatus;
  linkedReviewCount: number;
  latestDecisionState?: string;
  latestOutcomeQuality?: string;
  latestValidationStatus?: string;
  latestPolicyEvent?: string;
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

export interface ReportSection {
  title: string;
  content: string;
  evidenceMode?: "observed"|"derived"|"simulated"|"user_asserted"|"mixed"|"unavailable";
  claimIds?: string[]; citationEvidenceIds?: string[]; verificationStatus?: "passed"|"partial"|"unverified"|"unavailable";
}

export interface ReportArtifact {
  packetId: string;
  ticker: string;
  title: string;
  createdAt: string;
  sections: ReportSection[];
  dataMode: "live" | "fallback" | "demo";
  provenanceLabel: string;
  marketDataSource: string | null;
  marketDataFreshnessSeconds: number | null;
  artifactId?: string | null;
  storageStatus?: string;
  contentHash?: string | null;
  schemaVersion?: string; asOf?: string|null; knowledgeCutoff?: string|null; modelDigest?: string|null; sourceSnapshotHash?: string|null;
  verifiedClaimCoverage?: number; unresolvedMaterialClaimCount?: number; rejectedClaimIds?: string[]; reportValidationStatus?: "passed"|"partial"|"legacy"|"failed";
  packetVersion?: number|null; apiBuildSha?: string|null; dbSchemaVersion?: string|null;
  proposalId?: string|null; admissionState?: string|null; reviewerDecisionHash?: string|null;
  degradedCapabilities?: string[]; requestId?: string|null;
}
export interface ReportDiff {
  packetId: string;
  beforePacketVersion: number;
  afterPacketVersion: number;
  beforeReportHash: string;
  afterReportHash: string;
  addedClaimIds: string[];
  correctedClaimIds: string[];
  rejectedClaimIds: string[];
  changedSections: string[];
  unchangedSections: string[];
  citationDelta: number;
  confidenceDelta: number;
  sectionClaimAttribution: Record<string, string[]>;
  numericalChanges: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  artifactId?: string | null;
  storageStatus?: string;
  contentHash?: string | null;
}
export interface TickerIdentity { ticker:string; canonicalTicker:string; instrumentId:string; exchangeMic?:string|null; securityType:string; effectiveFrom?:string|null; resolutionProvider:string; resolutionStatus:"verified"|"provisional"|"ambiguous"; }

// ---------------------------------------------------------------------------
// Job queue
// ---------------------------------------------------------------------------

export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface JobRecord {
  id: string;
  jobType: string;
  state: JobState;
  queuedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  inputSummary: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Market provider status
// ---------------------------------------------------------------------------

export interface MarketProviderStatus {
  name: string;
  type: "polygon" | "yahoo" | "demo";
  fallbackChain: string[];
  fallbackUsed: boolean;
  reason: string;
  polygonConfigured: boolean;
}

export interface RiskEvaluateRequest {
  activePositionSize: number;
  maxDrawdownThreshold: number;
}

export interface PacketOutcomeUpdate {
  outcome: string;
  outcome_date: string;
  pnl?: number;
  notes?: string;
}

export interface PortfolioContextUpdate {
  grossExposure: number;
  netExposure: number;
  longExposure: number;
  shortExposure: number;
  concentrationBySector: Record<string, number>;
  concentrationByFactor: Record<string, number>;
  relatedPositions: string[];
  factorOverlap: string[];
  riskBudgetRemaining: number;
  sizingConstraints: string[];
}

export interface ConfidenceDeriveRequest {
  evidenceScore?: number;
  technicalScore?: number;
  sentimentScore?: number;
  interMarketScore?: number;
  validationScore?: number;
  tradeabilityScore?: number;
  blockers?: string[];
}

export interface RetrievalHit {
  kind: "prior_review" | "packet_source" | "decision_memory";
  id: string;
  title: string;
  snippet: string;
  score: number;
  scoreComponents?: Record<string, number> | null;
}

export interface RetrievalResponse {
  packetId: string;
  query: string;
  results: RetrievalHit[];
}
