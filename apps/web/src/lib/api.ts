import type {
  BacktestPrepareRequest,
  BacktestRunRequest,
  ConfidenceDeriveRequest,
  DecisionMemoryRecord,
  DecisionPacket,
  JobRecord,
  MarketProviderStatus,
  PacketOutcomeUpdate,
  MarketSnapshot,
  PortfolioContextUpdate,
  PacketWorkflowStatus,
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
  TickerIdentity,
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

export class ApiRequestError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function isApiUnavailableStatus(status: number): boolean {
  return status === 404 || (status >= 500 && status !== 503);
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";

  if (!response.ok) {
    if (isApiUnavailableStatus(response.status)) {
      throw new ApiUnavailableError();
    }
    let detail = "";
    if (contentType.includes("application/json")) {
      try {
        const payload = await response.json() as { detail?: unknown };
        detail = formatApiErrorDetail(payload.detail);
      } catch {
        detail = "";
      }
    } else {
      try {
        detail = (await response.text()).trim();
      } catch {
        detail = "";
      }
    }
    throw new ApiRequestError(
      response.status,
      detail ? `API request failed: ${response.status} - ${detail}` : `API request failed: ${response.status}`,
    );
  }

  if (!contentType.includes("application/json")) {
    throw new ApiUnavailableError();
  }

  return response.json() as Promise<T>;
}

function formatApiErrorDetail(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const record = item as { loc?: unknown[]; msg?: string; type?: string };
        const location = Array.isArray(record.loc) ? record.loc.join(".") : "request";
        return `${location}: ${record.msg ?? record.type ?? "invalid value"}`;
      })
      .join("; ");
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
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
  const headers = new Headers(init?.headers);
  const method = (init?.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith("ambrosia_csrf="))
      ?.slice("ambrosia_csrf=".length);
    if (csrf && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", decodeURIComponent(csrf));
    }
  }

  try {
    return await fetch(input, {
      ...init,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof ApiUnavailableError || (error instanceof DOMException && error.name === "AbortError")) {
      throw new ApiUnavailableError();
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export type AccountSession = {
  user: { id: string; email: string; displayName?: string; professionalRole?: string };
  organization: { id: string; name: string; role: string };
  session: { id: string; expiresAt?: string; absoluteExpiresAt?: string };
};

type SignupResult = {
  status: "pending_verification";
  message: string;
  userId: string;
  organizationId: string;
  workspaceId: string;
  developmentVerificationToken?: string;
  deliveryStatus: "sent" | "retry_required";
};

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}${path}`, init, 20000);
  return readJsonResponse<T>(response);
}

export function signupAccount(body: {
  email: string;
  password: string;
  organizationName: string;
  displayName: string;
  professionalRole: string;
  acceptedTerms: boolean;
}): Promise<SignupResult> {
  return authRequest<SignupResult>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function resendAccountVerification(email: string): Promise<{ message: string; developmentVerificationToken?: string }> {
  return authRequest("/auth/resend-verification", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function verifyAccountEmail(token: string): Promise<AccountSession> {
  return authRequest<AccountSession>("/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export function loginAccount(email: string, password: string): Promise<AccountSession> {
  return authRequest<AccountSession>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function getAccountSession(): Promise<AccountSession> {
  return authRequest<AccountSession>("/auth/me");
}

export async function recordProductEvent(
  eventType: "onboarding_viewed" | "guided_started" | "own_thesis_started" | "packet_saved" | "review_completed" | "outcome_recorded" | "return_session",
  surface: string,
  options: {
    objectReference?: string;
    properties?: Record<string, string | number | boolean | null>;
  } = {},
): Promise<boolean> {
  try {
    const sessionKey = "ambrosia.analytics.session";
    let sessionId = window.sessionStorage.getItem(sessionKey);
    if (!sessionId) {
      sessionId = window.crypto.randomUUID();
      window.sessionStorage.setItem(sessionKey, sessionId);
    }
    let objectKey = "";
    if (options.objectReference) {
      const digest = await window.crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(options.objectReference),
      );
      objectKey = Array.from(new Uint8Array(digest).slice(0, 8))
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
    }
    const result = await authRequest<{ inserted: boolean }>("/analytics/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        eventType,
        surface,
        objectReference: options.objectReference,
        eventKey: `${sessionId}:${eventType}:${surface}:${objectKey}`.slice(0, 120),
        properties: options.properties ?? {},
      }),
    });
    return result.inserted;
  } catch {
    // Telemetry is deliberately best effort and never blocks the decision workflow.
    return false;
  }
}

export type ActivationReport = {
  windowDays: number;
  events: Record<string, { count: number; uniqueUsers: number }>;
};

export function getActivationReport(days = 30): Promise<ActivationReport> {
  return authRequest(`/analytics/activation?days=${encodeURIComponent(days)}`);
}

export type GovernedArtifactRecord = {
  id: string;
  artifact_kind: "exports" | "evidence" | "llm" | "reports";
  content_hash: string;
  size_bytes: number;
  storage_status: "pending" | "durable" | "failed";
  created_at: string;
};

export function listGovernedArtifacts(): Promise<{ artifacts: GovernedArtifactRecord[] }> {
  return authRequest("/artifacts");
}

export function getGovernedArtifactDownload(artifactId: string): Promise<{
  url: string;
  expiresInSeconds: number;
}> {
  return authRequest(`/artifacts/${encodeURIComponent(artifactId)}/download`);
}

export function requestPasswordReset(email: string): Promise<{
  message: string;
  developmentResetToken?: string;
}> {
  return authRequest("/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function resetAccountPassword(token: string, newPassword: string): Promise<{
  status: string;
  message: string;
}> {
  return authRequest("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, newPassword }),
  });
}

export async function logoutAccount(): Promise<void> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/auth/logout`, { method: "POST" }, 20000);
  if (!response.ok) {
    throw new Error(`Unable to sign out (${response.status})`);
  }
}

export type AccountSessionRecord = {
  id: string;
  current: boolean;
  createdAt?: string;
  lastSeenAt?: string;
  expiresAt: string;
  absoluteExpiresAt: string;
  ipPrefix?: string;
};

export function listAccountSessions(): Promise<{ sessions: AccountSessionRecord[] }> {
  return authRequest("/auth/sessions");
}

export function revokeAccountSession(sessionId: string): Promise<{ revoked: boolean }> {
  return authRequest(`/auth/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export async function logoutAllAccounts(): Promise<void> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/auth/logout-all`, { method: "POST" }, 20000);
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
}

export function updateAccountProfile(body: { displayName: string; professionalRole: string }): Promise<{ user: AccountSession["user"] }> {
  return authRequest("/auth/profile", {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

export function changeAccountPassword(currentPassword: string, newPassword: string): Promise<{ status: string; otherSessionsRevoked: boolean }> {
  return authRequest("/auth/change-password", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ currentPassword, newPassword }),
  });
}

export type TeamMemberRecord = {
  id: string;
  email: string;
  display_name: string;
  professional_role: string;
  role: string;
  status: string;
  created_at?: string;
};

export type InvitationRecord = {
  id: string;
  email: string;
  role: string;
  created_at?: string;
  expires_at?: string;
  deliveryStatus?: "sent" | "retry_required";
};

export function getTeam(): Promise<{ members: TeamMemberRecord[]; invitations: InvitationRecord[] }> {
  return authRequest("/team");
}

export function inviteTeamMember(email: string, role: string): Promise<InvitationRecord & { developmentInvitationToken?: string }> {
  return authRequest("/team/invitations", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
}

export function revokeTeamInvitation(id: string): Promise<{ revoked: boolean }> {
  return authRequest(`/team/invitations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function updateTeamMember(
  id: string,
  role: "viewer" | "analyst" | "reviewer" | "admin",
  status: "active" | "suspended",
): Promise<{ updated: boolean }> {
  return authRequest(`/team/members/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, status }),
  });
}

export function acceptTeamInvitation(body: {
  token: string;
  password?: string;
  displayName: string;
  professionalRole: string;
  acceptedTerms: boolean;
}): Promise<AccountSession> {
  return authRequest("/auth/accept-invite", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

export type LocalWorkerRecord = {
  id: string;
  name: string;
  status: string;
  last_seen_at?: string;
  created_at?: string;
};

export function listLocalWorkers(): Promise<{ workers: LocalWorkerRecord[] }> {
  return authRequest("/llm/workers");
}

export function createLocalWorker(name: string): Promise<{ id: string; name: string; token: string }> {
  return authRequest("/llm/workers", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
}

export function revokeLocalWorker(id: string): Promise<{ revoked: boolean }> {
  return authRequest(`/llm/workers/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export type LlmRunRecord = {
  id: string;
  job_id: string;
  model_name: string;
  model_digest?: string;
  verification_status: string;
  output_schema_version: string;
  content_hash: string;
  created_at: string;
};

export function listLlmRuns(): Promise<{ runs: LlmRunRecord[] }> {
  return authRequest("/llm/runs");
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
        source_pointer: input.sourcePointer,
        subject_type: input.subjectType,
        instrument_id: input.instrumentId
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
export async function getMarketIdentity(ticker:string):Promise<TickerIdentity>{const apiBaseUrl=getApiBaseUrl();if(!apiBaseUrl)throw new ApiUnavailableError();const safeTicker=normalizeTickerForPath(ticker);return readJsonResponse<TickerIdentity>(await fetchWithTimeout(`${apiBaseUrl}/market/${encodeURIComponent(safeTicker)}/identity`));}

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

export async function selectiveIntegratePacket(packetId: string): Promise<DecisionPacket> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    throw new ApiUnavailableError();
  }

  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/selective-integrate`, {
    method: "POST",
  });

  return readJsonResponse<DecisionPacket>(response);
}

export async function recordPacketDecision(
  packetId: string,
  body: { decision_state: string; rationale: string; actor?: string }
): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/decision", body);
}

export async function refreshPacketProvenance(packetId: string): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/provenance/refresh", {});
}

export async function runPacketDisconfirmation(packetId: string): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/disconfirmation/run", {});
}

export async function runPacketRiskGate(packetId: string): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/risk-gate/run", {});
}

export async function getPacketIntegrationStatus(packetId: string): Promise<PacketWorkflowStatus> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/integration/status`);
  return readJsonResponse<PacketWorkflowStatus>(response);
}

export async function getPacketMemory(packetId: string): Promise<DecisionMemoryRecord[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/memory`);
  return readJsonResponse<DecisionMemoryRecord[]>(response);
}

export async function resolvePacketMemory(
  packetId: string,
  body: {
    outcome: string;
    observedAt: string;
    score?: number | null;
    notes?: string | null;
    evidenceReferences?: string[];
    actor?: string;
  }
): Promise<DecisionPacket> {
  return postPacketAction(packetId, "/memory/resolve", body);
}

export async function verifyPacketAuditChain(
  packetId: string
): Promise<{ packetId: string; valid: boolean; eventCount: number; verifiedAt: string }> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/audit-chain/verify`);
  return readJsonResponse<{ packetId: string; valid: boolean; eventCount: number; verifiedAt: string }>(response);
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
  decisionAction?: "BUY" | "SELL" | "HOLD" | "HEDGE" | "RISK_ADJUST" | "BLOCK" | "RETIRE";
  decisionUse?: string[];
  instrumentAction?: Record<string, unknown>;
  riskBudgetId?: string;
  maxPositionSize?: number;
  maxDrawdownLimit?: number;
  hedgePlan?: string;
  riskAdjustment?: string;
  liquidityCheck?: string;
  costCheck?: string;
  approvalState?: string;
  executionReadiness?: string;
  outcomeWritebackRequired?: boolean;
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

export type ResearchObjectReference = {
  referenceId: string;
  snapshotId: string;
  objectType: "signal" | "hypothesis";
  objectId: string;
  versionId: number;
  snapshot: Record<string, unknown>;
  contentHash: string;
  relationshipType: "research_evidence" | "supports" | "challenges" | "disconfirms";
  actor: string;
  attachedAt: string;
  driftStatus: "current" | "superseded";
};

export async function attachResearchObjectReference(
  reviewId: string,
  body: {
    objectType: "signal" | "hypothesis";
    objectId: string;
    versionId?: number | "current";
    relationshipType?: ResearchObjectReference["relationshipType"];
  }
): Promise<ResearchObjectReference> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews/${encodeURIComponent(reviewId)}/research-object-references`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await readJsonResponse<{ reference: ResearchObjectReference }>(response);
  return payload.reference;
}

export async function listResearchObjectReferences(reviewId: string): Promise<ResearchObjectReference[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(`${apiBaseUrl}/reviews/${encodeURIComponent(reviewId)}/research-object-references`);
  const payload = await readJsonResponse<{ references: ResearchObjectReference[] }>(response);
  return payload.references;
}

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
