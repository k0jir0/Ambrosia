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