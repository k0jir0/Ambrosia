import { buildReviewCreatePayload, buildReviewInputFromScannerCandidate, getApiBaseUrl, signalKey } from "../api";
import { buildSampleDataset } from "../sample-data";
import type { CreateReviewInput, SignalRecord } from "../types";

describe("mobile API helpers", () => {
  const originalProcess = globalThis.process;

  afterEach(() => {
    Object.defineProperty(globalThis, "process", {
      configurable: true,
      value: originalProcess
    });
  });

  it("resolves API URL from EXPO_PUBLIC_API_URL without trailing slash", () => {
    Object.defineProperty(globalThis, "process", {
      configurable: true,
      value: { env: { EXPO_PUBLIC_API_URL: "https://api.example.test/" } }
    });

    expect(getApiBaseUrl()).toBe("https://api.example.test");
  });

  it("maps review creation payload to FastAPI snake_case fields", () => {
    const input: CreateReviewInput = {
      thesis: "Mobile payload mapping should preserve the review request contract.",
      ticker: "SPY",
      assetClass: "ETF",
      timeHorizon: "1-4 weeks",
      intendedExpression: "Watchlist review",
      sourcePointer: "jest"
    };

    expect(buildReviewCreatePayload(input)).toEqual({
      thesis: input.thesis,
      ticker: "SPY",
      asset_class: "ETF",
      time_horizon: "1-4 weeks",
      intended_expression: "Watchlist review",
      source_pointer: "jest"
    });
  });

  it("routes scanner candidates into canonical review intake payloads", () => {
    const input = buildReviewInputFromScannerCandidate({
      ticker: "JPM",
      signal: "momentum_up",
      thesisSuggestion: "JPM requires adversarial review before action.",
      score: 0.82,
      price: 241.7,
      trend: "uptrend",
      rsi: 61,
      volume24h: 18400000,
      dataSource: "test",
      dataMode: "fallback",
      scannedAt: "2026-07-13T18:00:00Z"
    });

    expect(input).toMatchObject({
      ticker: "JPM",
      thesis: "JPM requires adversarial review before action.",
      intendedExpression: "Review before capital allocation",
      sourcePointer: "scanner:JPM:momentum_up:2026-07-13T18:00:00Z"
    });
  });

  it("uses stable signal IDs before falling back to name", () => {
    expect(signalKey({ signalId: "sig-1", id: "legacy", name: "Signal" } as SignalRecord)).toBe("sig-1");
    expect(signalKey({ id: "legacy", name: "Signal" } as SignalRecord)).toBe("legacy");
    expect(signalKey({ name: "Signal" } as SignalRecord)).toBe("Signal");
  });

  it("builds deterministic fallback data with visible sample source", () => {
    const dataset = buildSampleDataset("https://api.example.test");

    expect(dataset.source).toBe("sample");
    expect(dataset.apiUrl).toBe("https://api.example.test");
    expect(dataset.summary.pendingReviews).toBeGreaterThan(0);
    expect(dataset.priorityQueue.length).toBeGreaterThan(0);
  });
});
