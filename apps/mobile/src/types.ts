export type DecisionState = "pursue" | "watch" | "reject" | "needs_more_data";

export type ReviewStatus =
  | "intake"
  | "retrieval"
  | "adversarial_review"
  | "validation"
  | "tradeability"
  | "synthesis"
  | "decision_recorded";

export type DataSource = "api" | "sample";

export type ModuleId =
  | "today"
  | "reviews"
  | "scanner"
  | "signals"
  | "alpha"
  | "history"
  | "enterprise";

export interface Claim {
  id: string;
  kind: "sourced" | "assumption" | "inference" | "contradiction" | "unknown";
  text: string;
  evidence?: string;
  confidence: number;
}

export interface ValidationSpec {
  status: "specified" | "refused";
  hypothesis: string;
  nullHypothesis: string;
  dataRequirements: string[];
  protocol: string;
  refusalReason?: string;
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
  tradeability: Array<{
    topic: string;
    question: string;
    severity: "low" | "medium" | "high";
  }>;
  audit: Array<{
    id: string;
    timestamp: string;
    eventType: string;
    detail: string;
  }>;
  sources?: SourcePointer[];
}

export interface SourcePointer {
  id: string;
  title: string;
  sourceType: string;
  timestamp: string;
  permission: string;
  relevance: number;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  eventType: string;
  detail: string;
}

export interface ScannerCandidate {
  ticker: string;
  signal: string;
  thesisSuggestion: string;
  score: number;
  price: number;
  trend: string;
  rsi: number | null;
  volume24h: number;
  dataSource: string;
  dataMode: "live" | "fallback" | "demo";
  scannedAt: string;
}

export interface SignalRecord {
  signalId?: string;
  id?: string;
  name: string;
  status: string;
  version?: number;
  universe?: string[];
  horizon?: string;
  formula?: string;
  benchmark?: string;
  costModel?: string;
  latestDecisionState?: string | null;
  latestDecisionAction?: string | null;
  executionReadiness?: string | null;
  linkedReviewCount?: number;
  outcomeState?: string | null;
  updatedAt?: string;
}

export interface AlphaHypothesis {
  hypothesisId?: string;
  id?: string;
  title: string;
  signalFamily?: string;
  thesis?: string;
  universe?: string[];
  horizon?: string;
  status?: string;
  createdAt?: string;
}

export interface HealthStatus {
  status?: string;
  service?: string;
  version?: string;
  persistence?: {
    mode?: string;
    databaseConfigured?: boolean;
    databaseConnected?: boolean;
  };
}

export interface PriorityItem {
  kind: string;
  id: string;
  label: string;
  severity: "info" | "warning" | "critical" | string;
  nextAction: string;
}

export interface MobileSummary {
  pendingReviews: number;
  decidedReviews: number;
  activeSignals: number;
  scannerCandidates: number;
  alphaHypotheses: number;
  priorityItems: number;
}

export interface MobileDataset {
  source: DataSource;
  apiUrl: string;
  health: HealthStatus;
  summary: MobileSummary;
  priorityQueue: PriorityItem[];
  reviews: TradeReview[];
  scannerCandidates: ScannerCandidate[];
  signals: SignalRecord[];
  alphaHypotheses: AlphaHypothesis[];
  enterpriseStatus?: Record<string, unknown>;
  loadedAt: string;
}

export interface CreateReviewInput {
  thesis: string;
  ticker: string;
  assetClass: string;
  timeHorizon: string;
  intendedExpression: string;
  sourcePointer: string;
}

export interface MobileReviewSummary {
  schemaVersion: "mobile-review-summary.v1";
  review: {
    id: string;
    schemaVersion: string;
    workflowVersion: string;
    title: string;
    thesis: string;
    ticker: string;
    assetClass: string;
    timeHorizon: string;
    intendedExpression: string;
    status: ReviewStatus | string;
    decisionState: DecisionState | null;
    confidence: number;
    followUpDate: string;
    createdAt: string;
    strongestCritique: string;
    disconfirmingTest: string;
    validation: ValidationSpec;
    tradeability: TradeReview["tradeability"];
    claimCount: number;
    sourceCount: number;
    auditCount: number;
  };
  historicalAnalogue: TradeReview["historicalAnalogue"];
  claims: Claim[];
  sources: SourcePointer[];
  audit: AuditEvent[];
  runbook: Array<{
    id: string;
    label: string;
    status: "complete" | "pending" | "blocked" | string;
    detail: string;
  }>;
  providerProvenance: {
    mode: string;
    fallbackUsed: boolean;
    sourceCount: number;
    auditCount: number;
    provider: string;
    lastAuditEvent?: AuditEvent | null;
  };
  riskGate: {
    status: string;
    hardBlockCount: number;
    highSeverityCount: number;
    tradeabilityQuestions: TradeReview["tradeability"];
    requiresServerConfirmation: boolean;
    executionAuthority: string;
  };
  signalWriteback: {
    status: string;
    requiresLinkedSignal: boolean;
    canWriteDecision: boolean;
    suggestedAction: string;
    decisionState: DecisionState | null;
    executionReadiness: string;
  };
  reportStatus: {
    status: string;
    latestEvent?: AuditEvent | null;
    exportAvailable: boolean;
    desktopRoute: string;
  };
  hardBlocks: string[];
  softAdvisories: string[];
  canPursue: boolean;
  availableDecisionStates: DecisionState[];
  nextAction: string;
  freshness: string;
  updatedAt: string;
}

export interface MobileSignalDecisionReadiness {
  schemaVersion: "mobile-signal-decision-readiness.v1";
  signal: SignalRecord;
  decisionReadiness: string;
  nextAction: string;
  hardBlocks: string[];
  validationRuns: Array<Record<string, unknown>>;
  policyEvents: Array<Record<string, unknown>>;
  decisionLinks: Array<Record<string, unknown>>;
  outcomeRollup: Record<string, unknown>;
  alphaContext: Record<string, unknown>;
  alphaDecay: Record<string, unknown>;
  humanDecisionAuthority: boolean;
  llmInLiveOrderLoop: boolean;
  updatedAt: string;
}
