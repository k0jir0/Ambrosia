import type { ThesisInput, TradeReview } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_API_TIMEOUT_MS = 2500;
const CREATE_REVIEW_TIMEOUT_MS = 8000;

export class ApiUnavailableError extends Error {
  constructor(message = "Ambrosia API unavailable; using local deterministic fallback.") {
    super(message);
    this.name = "ApiUnavailableError";
  }
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
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/reviews`,
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

  if (!response.ok) {
    throw new Error(`Review generation failed: ${response.status}`);
  }

  return response.json();
}

export async function listReviews(): Promise<TradeReview[]> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/reviews`);

  if (!response.ok) {
    throw new Error(`Review list failed: ${response.status}`);
  }

  return response.json();
}

export async function recordDecision(reviewId: string, decisionState: string): Promise<TradeReview> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/reviews/${reviewId}/decision`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision_state: decisionState })
  });

  if (!response.ok) {
    throw new Error(`Decision update failed: ${response.status}`);
  }

  return response.json();
}
