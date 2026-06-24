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
}

export interface DecisionPacket extends TradeReview {
  // New quant workflow agent fields
  marketSnapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  interMarket: InterMarketContext | null;
  fundamentals: FundamentalContext | null;
  backtestPlan: BacktestPlan;
  backtestResult: BacktestResult | null;
  riskMonitor: RiskMonitor | null;
  portfolioContext: PortfolioContext | null;
  confidenceBreakdown: ConfidenceComponents;
  
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
  };
  
  // Coordinator metadata
  coordinatorVersion: string;
  providerInfo: {
    name: string;
    type: "deterministic" | "ollama" | "hosted" | "hybrid";
    fallbackChain: string[];
  };
}