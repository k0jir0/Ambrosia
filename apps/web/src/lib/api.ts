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
  ReportDiff,
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
export const WEB_BUILD_SHA = process.env.NEXT_PUBLIC_BUILD_SHA ?? "development";
export const GOVERNED_REPORT_EXPORT_ENABLED = process.env.NEXT_PUBLIC_ENABLE_REVIEW_EXPORT === "true";
const DEFAULT_API_TIMEOUT_MS = 65000;
const CREATE_REVIEW_TIMEOUT_MS = 65000;

export class ApiUnavailableError extends Error {
  constructor(message = "Ambrosia API unavailable; using local deterministic fallback.") {
    super(message);
    this.name = "ApiUnavailableError";
  }
}

export type ApiErrorCode =
  | "API_UNREACHABLE" | "REQUEST_TIMEOUT" | "RESPONSE_CONTRACT_INVALID"
  | "API_VERSION_MISMATCH" | "AUTHENTICATION_REQUIRED" | "AUTHORIZATION_DENIED"
  | "CSRF_REJECTED" | "NOT_FOUND" | "VALIDATION_FAILED" | "PERSISTENCE_UNAVAILABLE"
  | "REPORT_EXPORT_DISABLED" | "ARTIFACT_STORAGE_UNAVAILABLE" | "KMS_ACCESS_DENIED"
  | "IDEMPOTENCY_KEY_REUSED" | "REPORT_GENERATION_IN_PROGRESS"
  | "PROPOSAL_CONTENT_RETAINED_DATA_DELETED"
  | "CORRECTION_REVERIFICATION_REQUIRED" | "CORRECTION_REVERIFICATION_FAILED"
  | "MARKET_DATA_UNAVAILABLE" | "MODEL_POLICY_UNCONFIGURED" | "NO_ENROLLED_WORKER"
  | "WORKER_OFFLINE" | "WORKER_REVOKED"
  | "DIGEST_MISMATCH" | "PREFLIGHT_INCOMPLETE" | "PROPOSAL_AWAITING_REVIEW"
  | "PROPOSAL_STALE" | "RATE_LIMITED" | "PAYLOAD_TOO_LARGE" | "INTERNAL_ERROR";

export type ApiProblem = {
  type: string; title: string; status: number; detail: unknown; instance: string;
  code: ApiErrorCode; requestId?: string; traceId?: string | null; retryable: boolean;
  dependency?: string; operationId?: string; packetId?: string;
  expectedVersion?: number; actualVersion?: number;
};

type ApiErrorPayload = Partial<ApiProblem> & { detail?: unknown };

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code: ApiErrorCode = "VALIDATION_FAILED",
    public readonly retryable = false,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class ApiProblemError extends ApiRequestError {
  constructor(public readonly problem: ApiProblem) {
    super(problem.status, `${problem.title}: ${formatApiErrorDetail(problem.detail)}`,
      problem.code, problem.retryable, problem.requestId);
    this.name = "ApiProblemError";
  }
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json") || contentType.includes("+json");

  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    if (isJson) {
      try {
        payload = await response.json() as ApiErrorPayload;
      } catch {
        payload = null;
      }
    }
    if (payload?.code && payload.title && payload.type) {
      throw new ApiProblemError({
        type: payload.type, title: payload.title, status: response.status,
        detail: payload.detail, instance: payload.instance ?? "unknown",
        code: payload.code, requestId: payload.requestId, traceId: payload.traceId,
        retryable: payload.retryable ?? false,
        dependency: payload.dependency,
        operationId: payload.operationId,
        packetId: payload.packetId,
        expectedVersion: payload.expectedVersion,
        actualVersion: payload.actualVersion,
      });
    }
    const detail = formatApiErrorDetail(payload?.detail);
    throw new ApiRequestError(
      response.status,
      detail ? `API request failed: ${response.status} - ${detail}` : `API request failed: ${response.status}`,
      response.status === 401 ? "AUTHENTICATION_REQUIRED"
        : response.status === 403 ? "AUTHORIZATION_DENIED"
        : response.status === 404 ? "NOT_FOUND"
        : response.status === 429 ? "RATE_LIMITED"
        : response.status >= 500 ? "INTERNAL_ERROR" : "VALIDATION_FAILED",
      [429, 502, 503, 504].includes(response.status),
      response.headers.get("x-request-id") ?? undefined,
    );
  }

  if (!isJson) {
    throw new ApiRequestError(
      response.status, "API response did not match the JSON contract.",
      "RESPONSE_CONTRACT_INVALID", false, response.headers.get("x-request-id") ?? undefined,
    );
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

async function apiLivenessReachable(): Promise<boolean> {
  const base = getApiBaseUrl();
  if (!base) return false;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${base}/live`, { credentials: "include", signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
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
    const timedOut = error instanceof ApiUnavailableError
      || (error instanceof DOMException && error.name === "AbortError");
    if (await apiLivenessReachable()) {
      throw new ApiRequestError(
        timedOut ? 504 : 502,
        timedOut ? "The request timed out while the API remained live." : "The request transport failed while the API remained live.",
        timedOut ? "REQUEST_TIMEOUT" : "RESPONSE_CONTRACT_INVALID", true,
      );
    }
    throw new ApiUnavailableError("Ambrosia API liveness probe failed.");
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

export type WorkerEnrollmentRecord = {
  enrollmentId: string;
  workerId: string;
  workerName: string;
  token: string;
  readiness: OllamaWorkerReadiness;
};

export type WorkerEnrollmentCredential = {
  enrollmentId: string;
  workerId: string;
  workerName: string;
  token: string;
};

export type WorkerEnrollmentStatus = {
  enrollmentId: string;
  worker: LocalWorkerRecord;
  readiness: OllamaWorkerReadiness;
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

export function rotateLocalWorker(id: string): Promise<{ id: string; name: string; token: string }> {
  return authRequest(`/llm/workers/${encodeURIComponent(id)}/rotate`, { method: "POST" });
}

export function createWorkerEnrollment(body: {
  name: string;
  requestedModelDigest?: string;
  requiredContextLength?: number;
}): Promise<WorkerEnrollmentRecord> {
  return authRequest("/llm/worker-enrollments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getWorkerEnrollmentStatus(
  enrollmentId: string,
  options: { requestedModelDigest?: string; requiredContextLength?: number } = {},
): Promise<WorkerEnrollmentStatus> {
  const params = new URLSearchParams();
  if (options.requestedModelDigest) params.set("requestedModelDigest", options.requestedModelDigest);
  if (options.requiredContextLength) params.set("requiredContextLength", String(options.requiredContextLength));
  return authRequest(`/llm/worker-enrollments/${encodeURIComponent(enrollmentId)}${params.toString() ? `?${params.toString()}` : ""}`);
}

export function rotateWorkerEnrollment(enrollmentId: string): Promise<WorkerEnrollmentCredential> {
  return authRequest(`/llm/worker-enrollments/${encodeURIComponent(enrollmentId)}/rotate`, {
    method: "POST",
  });
}

export function runWorkerEnrollmentCanary(
  enrollmentId: string,
  body: { requestedModelDigest?: string; requiredContextLength?: number },
): Promise<{ enrollmentId: string; job: LlmJobStatus; readiness: OllamaWorkerReadiness }> {
  return authRequest(`/llm/worker-enrollments/${encodeURIComponent(enrollmentId)}/canary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
  if (providerMode !== "ollama") return postPacketAction(packetId, "/agents/run", { providerMode });
  let operation = await createAgentOperation(packetId);
  let delay = 1000;
  const deadline = Date.now() + 15 * 60 * 1000;
  while (!TERMINAL.has(operation.state) && Date.now() < deadline) {
    await new Promise((resolve) => window.setTimeout(resolve, delay));
    operation = await getAgentOperation(operation.id);
    delay = Math.min(10000, Math.round(delay * 1.5));
  }
  if (operation.state !== "completed") throw new ApiRequestError(409, operation.error?.message ?? `Ollama review ${operation.state}`);
  return getPacket(packetId);
}

export type AdmissionState = "proposed" | "auto_admitted" | "awaiting_human_review" | "human_admitted" | "corrected_and_admitted" | "rejected" | "stale" | "rolled_back";
export type AgentOperation = { id: string; operationId: string; packetId: string; expectedPacketVersion: number; state: "queued" | "leased" | "running" | "verifying" | "repairing" | "retry_wait" | "completed" | "failed" | "dead_letter" | "expired" | "canceled" | "superseded"; stage: string; progress: number; requestedProvider: string; actualProvider?: string | null; workerId?: string | null; workerName?: string | null; modelName?: string | null; modelDigest?: string | null; verificationStatus?: string | null; proposalId?: string | null; admissionState?: AdmissionState | null; resultPacketVersion?: number | null; fallbackOperationId?: string | null; statusUrl: string; cancelUrl: string; traceparent: string; deadlineAt: string; createdAt: string; updatedAt: string; error?: { code: string; message: string } | null };
export type OllamaModelPolicy = { name?: string; digest: string; contextLength?: number; approved: boolean; default?: boolean; workerCompatibility?: OllamaWorkerReadiness };
export type OllamaWorkerReadiness = { ready: boolean; reasonCode: "ready" | "no_enrolled_worker" | "worker_offline" | "worker_revoked" | "preflight_incomplete" | "digest_mismatch" | "model_policy_ambiguous" | "tenant_identity_required"; compatibleCount: number; lastSeenAt?: string | null; lastHeartbeatAgeSeconds?: number | null; freshnessSeconds?: number; preflightCompletedAt?: string | null; preflightAgeSeconds?: number | null; preflightMaxAgeSeconds?: number; preflightExpired?: boolean; requiredContextLength?: number; maxQualifiedContextLength?: number; requiredPromptManifestHash?: string; requiredOutputSchemaHash?: string; requiredWorkerVersion?: string; policyCompatibilityMismatch?: boolean };
export type ProviderStatus = { activeTenantWorkerCompatible: boolean; ollamaWorkerReadiness: OllamaWorkerReadiness; ollamaModelPolicies: OllamaModelPolicy[]; [key: string]: unknown };
export type ProposalClaim = { claimId: string; text: string; supportingEvidenceIds?: string[]; contradictingEvidenceIds?: string[]; falsifier?: string; materiality?: string; admissionStatus?: string };
export type PacketMutationProposal = { id: string; operationId: string; runId: string; packetId: string; basePacketVersion: number; basePacketHash: string; evidencePackHash: string; modelName: string; modelDigest: string; workerId?: string | null; originalOutputHash: string; proposedPatchHash: string; originalOutputArtifactId?: string | null; retentionUntil?: string | null; deletionState?: "active" | "content_deleted"; originalOutput: { materialClaims?: ProposalClaim[]; [key: string]: unknown }; proposedPatch: Record<string, unknown>; deterministicFindings: Array<Record<string, unknown>>; admissionState: AdmissionState; resultPacketVersion?: number | null; rollbackPacketVersion?: number | null; reviewerDecisionHash?: string | null; evidenceSnapshot: Array<Record<string, unknown>>; reviewImpact: Array<{ claimId?: string; reportSection: string }>; claimDecisions: Array<Record<string, unknown>>; proposalEvents: Array<Record<string, unknown>>; createdAt: string };
export type ClaimDecision = { claimId: string; decision: "accept_as_proposed" | "accept_with_human_correction" | "reject"; correctedText?: string; supportingEvidenceIds?: string[]; falsifier?: string };
export type AdmissionRequest = { proposalId: string; expectedPacketVersion: number; expectedProposalHash: string; disposition: "accepted" | "corrected" | "rejected"; claimDecisions: ClaimDecision[]; rationale: string; unsupportedClaimCount?: number; citationIssueCount?: number; usefulnessScore?: number; correctionVerificationRunId?: string };
export type LlmJobStatus = { id: string; state: string; taskType: string; runId?: string | null; verificationStatus?: string | null };
export const TERMINAL_AGENT_OPERATION_STATES = new Set<AgentOperation["state"]>(["completed", "failed", "dead_letter", "expired", "canceled", "superseded"]);
const TERMINAL = TERMINAL_AGENT_OPERATION_STATES;
export async function getProviderStatus(
  requestedModelDigest?: string,
  requestedContextLength?: number,
  options: {
    requiredPromptManifestHash?: string;
    requiredOutputSchemaHash?: string;
    requiredWorkerVersion?: string;
  } = {},
): Promise<ProviderStatus> {
  const base = getApiBaseUrl();
  if (!base) throw new ApiUnavailableError();
  const params = new URLSearchParams();
  if (requestedModelDigest) params.set("requestedModelDigest", requestedModelDigest);
  if (requestedContextLength) params.set("requestedContextLength", String(requestedContextLength));
  if (options.requiredPromptManifestHash) params.set("requiredPromptManifestHash", options.requiredPromptManifestHash);
  if (options.requiredOutputSchemaHash) params.set("requiredOutputSchemaHash", options.requiredOutputSchemaHash);
  if (options.requiredWorkerVersion) params.set("requiredWorkerVersion", options.requiredWorkerVersion);
  const query = params.toString();
  return readJsonResponse(await fetchWithTimeout(`${base}/providers/status${query ? `?${query}` : ""}`));
}
export async function createAgentOperation(packetId: string, idempotencyKey = crypto.randomUUID(), requestedModelDigest?: string): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); const trace = crypto.randomUUID().replaceAll("-", "") + crypto.randomUUID().replaceAll("-", ""); const traceparent = `00-${trace.slice(0, 32)}-${trace.slice(32, 48)}-01`; return readJsonResponse(await fetchWithTimeout(`${base}/packets/${encodeURIComponent(packetId)}/agent-operations`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey, traceparent }, body: JSON.stringify({ providerMode: "ollama", requestedModelDigest, traceparent }) })); }
export async function getAgentOperation(id: string): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}`)); }
export async function getAgentOperationProposal(id: string): Promise<PacketMutationProposal> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/proposal`)); }
export async function admitAgentOperationProposal(id: string, body: AdmissionRequest, idempotencyKey = crypto.randomUUID()): Promise<AgentOperation> {
  const base = getApiBaseUrl();
  if (!base) throw new ApiUnavailableError();
  let request = body;
  if (body.disposition === "corrected" && !body.correctionVerificationRunId) {
    const queued = await readJsonResponse<LlmJobStatus>(await fetchWithTimeout(
      `${base}/operations/${encodeURIComponent(id)}/correction-verification`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ));
    const deadline = Date.now() + 12 * 60 * 1000;
    let status = queued;
    let delay = 1500;
    while (!["completed", "failed", "dead_letter", "expired", "canceled"].includes(status.state) && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      status = await readJsonResponse<LlmJobStatus>(await fetchWithTimeout(
        `${base}/llm/jobs/${encodeURIComponent(queued.id)}`,
      ));
      delay = Math.min(8000, Math.round(delay * 1.5));
    }
    if (status.state !== "completed" || status.verificationStatus !== "passed" || !status.runId) {
      throw new ApiRequestError(
        409,
        `Corrected claims were not independently verified (job ${status.id}: ${status.state}).`,
        "CORRECTION_REVERIFICATION_FAILED",
        status.state === "queued" || status.state === "retry_wait",
      );
    }
    request = { ...body, correctionVerificationRunId: status.runId };
  }
  return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/admission`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(request),
  }));
}
export async function rollbackAgentOperationProposal(id: string, expectedPacketVersion: number, rationale: string, idempotencyKey = crypto.randomUUID()): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/rollback`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ expectedPacketVersion, rationale }) })); }
export async function cancelAgentOperation(id: string): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/cancel`, { method: "POST" })); }
export async function fallbackAgentOperation(id: string): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/fallback`, { method: "POST" })); }
export async function continueAgentOperation(id: string): Promise<AgentOperation> { const base = getApiBaseUrl(); if (!base) throw new ApiUnavailableError(); return readJsonResponse(await fetchWithTimeout(`${base}/operations/${encodeURIComponent(id)}/continue`, { method: "POST" })); }

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

const reportIdempotencyKeys = new Map<string, string>();

export async function generateReport(packetId: string): Promise<ReportArtifact> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  let idempotencyKey = reportIdempotencyKeys.get(packetId);
  if (!idempotencyKey) {
    idempotencyKey = crypto.randomUUID();
    reportIdempotencyKeys.set(packetId, idempotencyKey);
  }
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/report`,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
  );
  const report = await readJsonResponse<ReportArtifact>(response);
  if (!["ticker-intelligence-report.v1", "ticker-intelligence-report.v2"].includes(report.schemaVersion ?? "")) {
    throw new ApiRequestError(502, "Unsupported report schema returned by API.", "RESPONSE_CONTRACT_INVALID");
  }
  if (!report.reportValidationStatus || report.reportValidationStatus === "failed") {
    throw new ApiRequestError(502, "Report validation did not pass the governed API contract.", "RESPONSE_CONTRACT_INVALID");
  }
  if (GOVERNED_REPORT_EXPORT_ENABLED
      && (!report.artifactId || !report.contentHash || report.storageStatus !== "durable")) {
    throw new ApiRequestError(503, "Governed report did not include durable artifact evidence.", "ARTIFACT_STORAGE_UNAVAILABLE", true, report.requestId ?? undefined);
  }
  return report;
}

export async function generateReportDiff(packetId: string): Promise<ReportDiff> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/packets/${encodeURIComponent(packetId)}/report/diff`,
    { method: "POST" },
  );
  return readJsonResponse<ReportDiff>(response);
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

export type DeploymentCapabilities = {
  schemaVersion: "deployment-capabilities.v1";
  buildSha: string;
  dbSchemaVersion: string;
  apiBasePath: string;
  reportExport: { enabled: boolean; writable: boolean; reasonCode: string; lastProbeAt?: string | null };
  marketData: Record<string, unknown>;
  ollamaWorker: OllamaWorkerReadiness;
};

export async function getDeploymentCapabilities(requestedModelDigest?: string): Promise<DeploymentCapabilities> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new ApiUnavailableError();
  const query = requestedModelDigest ? `?requested_model_digest=${encodeURIComponent(requestedModelDigest)}` : "";
  const value = await readJsonResponse<DeploymentCapabilities>(
    await fetchWithTimeout(`${apiBaseUrl}/capabilities${query}`),
  );
  if (WEB_BUILD_SHA !== "development" && value.buildSha !== WEB_BUILD_SHA) {
    throw new ApiRequestError(409, "Web and API builds do not match.", "API_VERSION_MISMATCH", false);
  }
  if (GOVERNED_REPORT_EXPORT_ENABLED !== value.reportExport.enabled) {
    throw new ApiRequestError(409, "Web and API report-export policies do not match.", "API_VERSION_MISMATCH", false);
  }
  return value;
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
