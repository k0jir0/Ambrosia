import type {
  BacktestPrepareRequest,
  BacktestRunRequest,
  ConfidenceDeriveRequest,
  DecisionPacket,
  JobRecord,
  MarketProviderStatus,
  PacketOutcomeUpdate,
  MarketSnapshot,
  PortfolioContextUpdate,
  ProviderMode,
  ReportArtifact,
  RetrievalResponse,
  ScannerCandidatePromoteRequest,
  ScannerCandidatePromotion,
  RiskEvaluateRequest,
  ScannerResult,
  ScannerRunRequest,
  SentimentData,
  TechnicalIndicators,
  ThesisInput,
  TradeReview,
} from "./types";

const CONFIGURED_API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL)?.trim();
const DEFAULT_API_TIMEOUT_MS = 65000;
const CREATE_REVIEW_TIMEOUT_MS = 65000;

export class ApiUnavailableError extends Error {
  constructor(message = "Ambrosia API unavailable; using local deterministic fallback.") {
    super(message);
    this.name = "ApiUnavailableError";
  }
}

function isApiUnavailableStatus(status: number): boolean {
  return status === 404 || status >= 500;
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";

  if (!response.ok) {
    if (isApiUnavailableStatus(response.status)) {
      throw new ApiUnavailableError();
    }
    throw new Error(`API request failed: ${response.status}`);
  }

  if (!contentType.includes("application/json")) {
    throw new ApiUnavailableError();
  }

  return response.json() as Promise<T>;
}

export function getApiBaseUrl(): string | null {
  if (CONFIGURED_API_BASE_URL) {
    return CONFIGURED_API_BASE_URL.replace(/\/$/, "");
  }

  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:8000";
  }

  return null;
}

function normalizeTickerForPath(ticker: string): string {
  return ticker.replace(/\//g, " ").replace(/\s+/g, " ").trim();
}

async function fetchWithTimeout(input: RequestInfo | URL, init?: RequestInit, timeoutMs = DEFAULT_API_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(new ApiUnavailableError()), timeoutMs);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof ApiUnavailableError || (error instanceof DOMException && error.name === "AbortError")) {
      throw new ApiUnavailableError();
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function createReview(input: ThesisInput): Promise<TradeReview> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(
    `${apiBaseUrl}/reviews`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thesis: input.thesis,
        ticker: input.ticker,
        asset_class: input.assetClass,
        time_horizon: input.timeHorizon,
        intended_expression: input.intendedExpression,
        source_pointer: input.sourcePointer
      })
    },
    CREATE_REVIEW_TIMEOUT_MS
  );

  return readJsonResponse<TradeReview>(response);
}

export async function listReviews(): Promise<TradeReview[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews`);

  return readJsonResponse<TradeReview[]>(response);
}

export async function getReview(reviewId: string): Promise<TradeReview> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews/${encodeURIComponent(reviewId)}`);

  return readJsonResponse<TradeReview>(response);
}

export async function recordDecision(reviewId: string, decisionState: string): Promise<TradeReview> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews/${reviewId}/decision`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision_state: decisionState })
  });

  return readJsonResponse<TradeReview>(response);
}

export async function getMarketSnapshot(ticker: string): Promise<MarketSnapshot> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const safeTicker = normalizeTickerForPath(ticker);
  const response = await fetchWithTimeout(`${apiBaseUrl}/market/${encodeURIComponent(safeTicker)}/snapshot`);
  return readJsonResponse<MarketSnapshot>(response);
}

export async function getMarketTechnicals(ticker: string): Promise<TechnicalIndicators> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const safeTicker = normalizeTickerForPath(ticker);
  const response = await fetchWithTimeout(`${apiBaseUrl}/market/${encodeURIComponent(safeTicker)}/technicals`);
  return readJsonResponse<TechnicalIndicators>(response);
}

export async function getSentiment(ticker: string): Promise<SentimentData> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const safeTicker = normalizeTickerForPath(ticker);
  const response = await fetchWithTimeout(`${apiBaseUrl}/sentiment/${encodeURIComponent(safeTicker)}`);
  return readJsonResponse<SentimentData>(response);
}

export async function getPacket(packetId: string): Promise<DecisionPacket> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}`);
  return readJsonResponse<DecisionPacket>(response);
}

export async function createPacket(packet: DecisionPacket): Promise<DecisionPacket> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(packet),
  });

  return readJsonResponse<DecisionPacket>(response);
}

async function postPacketAction<TBody>(packetId: string, route: string, body: TBody): Promise<DecisionPacket> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}${route}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return readJsonResponse<DecisionPacket>(response);
}

export async function refreshPacketMetrics(packetId: string): Promise<DecisionPacket> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/metrics/refresh`, {
    method: "POST",
  });
  return readJsonResponse<DecisionPacket>(response);
}

export async function runPacketAgents(packetId: string, providerMode: ProviderMode = "deterministic"): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/agents/run", { providerMode });
}

export async function preparePacketBacktest(packetId: string, body: BacktestPrepareRequest): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/backtest/prepare", body);
}

export async function runPacketBacktest(packetId: string, body: BacktestRunRequest = { forceRun: false }): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/backtest/run", body);
}

export async function evaluatePacketRisk(packetId: string, body: RiskEvaluateRequest): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/risk/evaluate", body);
}

export async function recordPacketOutcome(packetId: string, body: PacketOutcomeUpdate): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/outcome", body);
}

export async function updatePacketPortfolio(packetId: string, body: PortfolioContextUpdate): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/portfolio/update", body);
}

export async function derivePacketConfidence(packetId: string, body: ConfidenceDeriveRequest): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/confidence/derive", body);
}

export async function retrievePacketContext(packetId: string, query: string, topK = 5): Promise<RetrievalResponse> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, topK }),
  });

  return readJsonResponse<RetrievalResponse>(response);
}

// ---------------------------------------------------------------------------
// Scanner
// ---------------------------------------------------------------------------

export async function runScanner(body: ScannerRunRequest = {}): Promise<ScannerResult> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/scanner/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<ScannerResult>(response);
}

export async function runScannerAsync(body: ScannerRunRequest = {}): Promise<JobRecord> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/scanner/run/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<JobRecord>(response);
}

export async function promoteScannerCandidateToAlpha(body: ScannerCandidatePromoteRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/scanner/candidates/promote-alpha`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function listScannerCandidatePromotions(): Promise<ScannerCandidatePromotion[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/scanner/candidates/promotions`);
  return readJsonResponse<ScannerCandidatePromotion[]>(response);
}

// ---------------------------------------------------------------------------
// Job queue
// ---------------------------------------------------------------------------

export async function getJobStatus(jobId: string): Promise<JobRecord> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}`);
  return readJsonResponse<JobRecord>(response);
}

export async function listJobs(): Promise<JobRecord[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/jobs`);
  return readJsonResponse<JobRecord[]>(response);
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

export async function generateReport(packetId: string): Promise<ReportArtifact> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/report`,
    { method: "POST" },
  );
  return readJsonResponse<ReportArtifact>(response);
}

// ---------------------------------------------------------------------------
// Market provider status & health
// ---------------------------------------------------------------------------

export async function getMarketProviderStatus(): Promise<MarketProviderStatus> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/market/providers/status`);
  return readJsonResponse<MarketProviderStatus>(response);
}

export async function getHealthDetailed(): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/health/detailed`);
  return readJsonResponse<Record<string, unknown>>(response);
}

// ---------------------------------------------------------------------------
// Signal + adversarial review integration
// ---------------------------------------------------------------------------

type SignalReviewLinkRequest = {
  reviewId: string;
  hypothesisId?: string;
  signalVersion?: number;
};

type SignalVersionCreateRequest = {
  horizon?: string;
  formula?: string;
  universe?: string[];
  costModel?: string;
  benchmark?: string;
  validationGates?: string[];
  createdBy?: string;
};

type SignalCreateRequest = {
  signalId?: string;
  name: string;
  universe?: string[];
  horizon?: string;
  formula: string;
  costModel?: string;
  benchmark?: string;
  validationGates?: string[];
};

type AlphaHypothesisCreateRequest = {
  hypothesisId?: string;
  title: string;
  signalFamily: string;
  universe?: string[];
  horizon?: string;
  thesis: string;
  planQuality?: string;
  disconfirmingTests?: string[];
  costModel?: string;
  owner?: string;
};

type SignalDecisionWritebackRequest = {
  reviewId: string;
  signalVersion?: number;
  decisionState: string;
  rationale?: string;
  overrideUsed?: boolean;
  decisionQuality?: string;
  evidenceLinks?: string[];
  verifierStatus?: string;
  reviewDate?: string;
};

type SignalOutcomeWritebackRequest = {
  reviewId: string;
  signalVersion?: number;
  outcomeQuality: string;
  lastReviewedAt?: string;
};

export async function linkSignalReview(signalId: string, body: SignalReviewLinkRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/link-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function writebackSignalDecision(signalId: string, body: SignalDecisionWritebackRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/writeback-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function writebackSignalOutcome(signalId: string, body: SignalOutcomeWritebackRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/writeback-outcome`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function createSignal(body: SignalCreateRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function createAlphaHypothesis(body: AlphaHypothesisCreateRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/alpha/hypotheses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function createSignalVersion(signalId: string, body: SignalVersionCreateRequest): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function listSignalVersions(signalId: string): Promise<Record<string, unknown>[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/versions`);
  return readJsonResponse<Record<string, unknown>[]>(response);
}

export async function linkAlphaHypothesisSignal(
  hypothesisId: string,
  body: { signalId: string; signalVersion?: number }
): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/alpha/hypotheses/${encodeURIComponent(hypothesisId)}/link-signal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function listAlphaHypothesisSignals(hypothesisId: string): Promise<Record<string, unknown>[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/alpha/hypotheses/${encodeURIComponent(hypothesisId)}/signals`);
  return readJsonResponse<Record<string, unknown>[]>(response);
}

export async function validateSignal(
  signalId: string,
  body: {
    signalVersion?: number;
    runType?: string;
    sampleWindows?: Record<string, string>;
    pointInTimeGuaranteed?: boolean;
    includesCosts?: boolean;
    includesSlippage?: boolean;
    includesLiquidity?: boolean;
  } = {}
): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function listSignalValidationRuns(signalId: string): Promise<Record<string, unknown>[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/validation-runs`);
  return readJsonResponse<Record<string, unknown>[]>(response);
}

async function transitionSignalPolicy(
  signalId: string,
  action: "promote" | "constrain" | "retire",
  body: { signalVersion?: number; actor?: string; reason?: string } = {}
): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function promoteSignal(signalId: string, body: { signalVersion?: number; actor?: string; reason?: string } = {}): Promise<Record<string, unknown>> {
  return transitionSignalPolicy(signalId, "promote", body);
}

export async function constrainSignal(signalId: string, body: { signalVersion?: number; actor?: string; reason?: string } = {}): Promise<Record<string, unknown>> {
  return transitionSignalPolicy(signalId, "constrain", body);
}

export async function retireSignal(signalId: string, body: { signalVersion?: number; actor?: string; reason?: string } = {}): Promise<Record<string, unknown>> {
  return transitionSignalPolicy(signalId, "retire", body);
}

export async function listSignalPolicyEvents(signalId: string): Promise<Record<string, unknown>[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/policy-events`);
  return readJsonResponse<Record<string, unknown>[]>(response);
}

export async function getSignalsProgramMetrics(): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/program-metrics`);
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function getSignalQualityScorecardWeekly(): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/quality-scorecard/weekly`);
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function seedIndex97Signals(): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/signals/seed-index97`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return readJsonResponse<Record<string, unknown>>(response);
}

export async function seedIndex97Reviews(): Promise<Record<string, unknown>> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews/seed-index97`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return readJsonResponse<Record<string, unknown>>(response);
}
