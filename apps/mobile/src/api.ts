import { buildSampleDataset } from "./sample-data";
import { getAccessToken } from "./auth";
import { readCachedDataset, writeCachedDataset } from "./storage";
import type {
  AlphaHypothesis,
  CreateReviewInput,
  DecisionState,
  HealthStatus,
  MobileDataset,
  MobileReviewSummary,
  MobileSignalDecisionReadiness,
  MobileSummary,
  PriorityItem,
  ScannerCandidate,
  SignalRecord,
  TradeReview
} from "./types";

const DEFAULT_API_URL = "http://127.0.0.1:8000";

type MobileTodayPayload = {
  source?: "api";
  loadedAt?: string;
  health?: HealthStatus;
  summary?: MobileSummary;
  priorityQueue?: PriorityItem[];
  recentReviews?: TradeReview[];
  scannerCandidates?: ScannerCandidate[];
  signals?: SignalRecord[];
  alphaHypotheses?: AlphaHypothesis[];
  enterpriseStatus?: Record<string, unknown>;
};

function getRuntimeEnv(): Record<string, string | undefined> {
  return (
    (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {}
  );
}

export function getApiBaseUrl(): string {
  return (getRuntimeEnv().EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL).replace(/\/$/, "");
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const target = `${getApiBaseUrl()}${path}`;
  const accessToken = await getAccessToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.body ? { "Content-Type": "application/json" } : {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
  };
  if (init?.headers && !Array.isArray(init.headers) && !(init.headers instanceof Headers)) {
    Object.assign(headers, init.headers);
  }

  const response = await fetch(target, {
    ...init,
    headers
  });

  const contentType = response.headers.get("content-type") ?? "";
  if (!response.ok) {
    throw new Error(`Ambrosia API ${response.status}: ${target}`);
  }
  if (!contentType.includes("application/json")) {
    throw new Error(`Ambrosia API returned non-JSON response: ${target}`);
  }
  return response.json() as Promise<T>;
}

async function tryRead<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  try {
    return await requestJson<T>(path, init);
  } catch {
    return fallback;
  }
}

export async function loadMobileDataset(): Promise<MobileDataset> {
  const apiUrl = getApiBaseUrl();
  const sample = buildSampleDataset(apiUrl);

  try {
    const [today, reviews, scanner, signals, alphaHypotheses] = await Promise.all([
      requestJson<MobileTodayPayload>("/mobile/today"),
      requestJson<TradeReview[]>("/reviews"),
      tryRead<{ candidates?: ScannerCandidate[] }>(
        "/scanner/run",
        { candidates: sample.scannerCandidates },
        {
          method: "POST",
          body: JSON.stringify({
            universe: ["AAPL", "MSFT", "NVDA", "JPM", "SOXX", "SPY"],
            maxCandidates: 8
          })
        }
      ),
      tryRead<SignalRecord[]>("/signals", sample.signals),
      tryRead<AlphaHypothesis[]>("/alpha/hypotheses", sample.alphaHypotheses)
    ]);

    const scannerCandidates = scanner.candidates ?? sample.scannerCandidates;
    const effectiveSignals = today.signals ?? signals;
    const effectiveAlphaHypotheses = today.alphaHypotheses ?? alphaHypotheses;

    const dataset: MobileDataset = {
      source: "api",
      apiUrl,
      health: today.health ?? { status: "ok", service: "ambrosia-api" },
      summary: {
        ...(today.summary ?? {
        pendingReviews: reviews.filter((review) => review.decisionState === null).length,
        decidedReviews: reviews.filter((review) => review.decisionState !== null).length,
        activeSignals: effectiveSignals.filter((signal) => !["retired", "blocked"].includes(signal.status)).length,
        scannerCandidates: scannerCandidates.length,
        alphaHypotheses: effectiveAlphaHypotheses.length,
        priorityItems: today.priorityQueue?.length ?? 0
        }),
        scannerCandidates: scannerCandidates.length
      },
      priorityQueue: today.priorityQueue ?? [],
      reviews,
      scannerCandidates,
      signals: effectiveSignals,
      alphaHypotheses: effectiveAlphaHypotheses,
      enterpriseStatus: today.enterpriseStatus,
      loadedAt: today.loadedAt ?? new Date().toISOString()
    };
    await writeCachedDataset(dataset);
    return dataset;
  } catch {
    const cached = await readCachedDataset();
    if (cached) {
      return {
        ...cached,
        source: "sample",
        health: {
          ...cached.health,
          status: "cached"
        },
        loadedAt: cached.loadedAt
      };
    }
    return sample;
  }
}

export function buildReviewCreatePayload(input: CreateReviewInput): Record<string, string> {
  return {
    thesis: input.thesis,
    ticker: input.ticker,
    asset_class: input.assetClass,
    time_horizon: input.timeHorizon,
    intended_expression: input.intendedExpression,
    source_pointer: input.sourcePointer
  };
}

export function buildReviewInputFromScannerCandidate(candidate: ScannerCandidate): CreateReviewInput {
  return {
    thesis: candidate.thesisSuggestion,
    ticker: candidate.ticker,
    assetClass: "US equities",
    timeHorizon: "1-4 weeks",
    intendedExpression: "Review before capital allocation",
    sourcePointer: `scanner:${candidate.ticker}:${candidate.signal}:${candidate.scannedAt}`
  };
}

export async function createReview(input: CreateReviewInput): Promise<TradeReview> {
  return requestJson<TradeReview>("/reviews", {
    method: "POST",
    body: JSON.stringify(buildReviewCreatePayload(input))
  });
}

export async function getReviewSummary(reviewId: string): Promise<MobileReviewSummary> {
  return requestJson<MobileReviewSummary>(`/mobile/reviews/${encodeURIComponent(reviewId)}/summary`);
}

export async function recordReviewDecision(reviewId: string, decisionState: DecisionState): Promise<TradeReview> {
  return requestJson<TradeReview>(`/reviews/${encodeURIComponent(reviewId)}/decision`, {
    method: "PATCH",
    body: JSON.stringify({ decision_state: decisionState })
  });
}

export async function recordReviewOutcome(reviewId: string, outcome: string, outcomeDate: string): Promise<TradeReview> {
  return requestJson<TradeReview>(`/reviews/${encodeURIComponent(reviewId)}/outcome`, {
    method: "POST",
    body: JSON.stringify({ outcome, outcome_date: outcomeDate })
  });
}

export async function getSignalDecisionReadiness(signalId: string): Promise<MobileSignalDecisionReadiness> {
  return requestJson<MobileSignalDecisionReadiness>(
    `/mobile/signals/${encodeURIComponent(signalId)}/decision-readiness`
  );
}

export async function validateSignal(signalId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/validate`, {
    method: "POST",
    body: JSON.stringify({
      runType: "mobile_triage_validation",
      pointInTimeGuaranteed: true,
      includesCosts: true,
      includesSlippage: true,
      includesLiquidity: true
    })
  });
}

export async function promoteSignal(signalId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/promote`, {
    method: "POST",
    body: JSON.stringify({
      actor: "mobile",
      reason: "Mobile policy promotion request after validation."
    })
  });
}

export async function constrainSignal(signalId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/constrain`, {
    method: "POST",
    body: JSON.stringify({
      actor: "mobile",
      reason: "Mobile policy constraint after readiness review."
    })
  });
}

export async function retireSignal(signalId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/retire`, {
    method: "POST",
    body: JSON.stringify({
      actor: "mobile",
      reason: "Mobile policy retirement after readiness review."
    })
  });
}

export async function linkSignalReview(signalId: string, reviewId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/link-review`, {
    method: "POST",
    body: JSON.stringify({
      reviewId
    })
  });
}

export async function writebackSignalDecision(
  signalId: string,
  reviewId: string,
  decisionState: DecisionState
): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/writeback-decision`, {
    method: "POST",
    body: JSON.stringify({
      reviewId,
      decisionState,
      decisionAction: decisionState === "pursue" ? "HOLD" : "BLOCK",
      decisionUse: ["mobile_review"],
      decisionQuality: decisionState === "pursue" ? "D3" : "D2",
      evidenceLinks: decisionState === "pursue" ? [`mobile-review:${reviewId}`] : [],
      verifierStatus: decisionState === "pursue" ? "passed" : null,
      reviewDate: decisionState === "pursue" ? new Date().toISOString().slice(0, 10) : null,
      approvalState: "mobile_recorded",
      executionReadiness: decisionState === "pursue" ? "paper_trade_ready" : "not_executable",
      rationale: "Mobile review decision writeback."
    })
  });
}

export async function writebackSignalOutcome(
  signalId: string,
  reviewId: string,
  outcomeQuality = "O1_mobile_checkpoint"
): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/signals/${encodeURIComponent(signalId)}/writeback-outcome`, {
    method: "POST",
    body: JSON.stringify({
      reviewId,
      outcomeQuality,
      lastReviewedAt: new Date().toISOString()
    })
  });
}

export async function getEnterpriseStatus(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/mobile/enterprise/status");
}

export async function promoteScannerCandidate(candidate: ScannerCandidate): Promise<{
  hypothesis?: AlphaHypothesis;
  signal?: SignalRecord;
  promotion?: Record<string, unknown>;
}> {
  return requestJson<{
    hypothesis?: AlphaHypothesis;
    signal?: SignalRecord;
    promotion?: Record<string, unknown>;
  }>("/scanner/candidates/promote-alpha", {
    method: "POST",
    body: JSON.stringify({
      ticker: candidate.ticker,
      signal: candidate.signal,
      thesisSuggestion: candidate.thesisSuggestion,
      score: candidate.score,
      price: candidate.price,
      trend: candidate.trend,
      rsi: candidate.rsi,
      volume: candidate.volume24h,
      universe: [candidate.ticker],
      promotedBy: "mobile"
    })
  });
}

export function signalKey(signal: SignalRecord): string {
  return signal.signalId ?? signal.id ?? signal.name;
}

export function alphaKey(alpha: AlphaHypothesis): string {
  return alpha.hypothesisId ?? alpha.id ?? alpha.title;
}
