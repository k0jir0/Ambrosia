import type { ThesisInput, TradeReview } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function createReview(input: ThesisInput): Promise<TradeReview> {
  const response = await fetch(`${API_BASE_URL}/reviews`, {
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
  });

  if (!response.ok) {
    throw new Error(`Review generation failed: ${response.status}`);
  }

  return response.json();
}

export async function listReviews(): Promise<TradeReview[]> {
  const response = await fetch(`${API_BASE_URL}/reviews`);

  if (!response.ok) {
    throw new Error(`Review list failed: ${response.status}`);
  }

  return response.json();
}

export async function recordDecision(reviewId: string, decisionState: string): Promise<TradeReview> {
  const response = await fetch(`${API_BASE_URL}/reviews/${reviewId}/decision`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision_state: decisionState })
  });

  if (!response.ok) {
    throw new Error(`Decision update failed: ${response.status}`);
  }

  return response.json();
}