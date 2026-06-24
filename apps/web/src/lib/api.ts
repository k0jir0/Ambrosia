import type {
  BacktestPrepareRequest,
  BacktestRunRequest,
  ConfidenceDeriveRequest,
  DecisionPacket,
  PacketOutcomeUpdate,
  MarketSnapshot,
  PortfolioContextUpdate,
  ProviderMode,
  RetrievalResponse,
  RiskEvaluateRequest,
  SentimentData,
  TechnicalIndicators,
  ThesisInput,
  TradeReview,
} from "./types";

const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
const DEFAULT_API_TIMEOUT_MS = 2500;
const CREATE_REVIEW_TIMEOUT_MS = 8000;

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

function getApiBaseUrl(): string | null {
  if (CONFIGURED_API_BASE_URL) {
    return CONFIGURED_API_BASE_URL.replace(/\/$/, "");
  }

  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:8000";
  }

  return null;
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

  const response = await fetchWithTimeout(`${apiBaseUrl}/market/${encodeURIComponent(ticker)}/snapshot`);
  return readJsonResponse<MarketSnapshot>(response);
}

export async function getMarketTechnicals(ticker: string): Promise<TechnicalIndicators> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/market/${encodeURIComponent(ticker)}/technicals`);
  return readJsonResponse<TechnicalIndicators>(response);
}

export async function getSentiment(ticker: string): Promise<SentimentData> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/sentiment/${encodeURIComponent(ticker)}`);
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
