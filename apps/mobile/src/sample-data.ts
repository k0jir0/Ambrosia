import type { MobileDataset, TradeReview } from "./types";

const now = new Date().toISOString();

export const sampleReviews: TradeReview[] = [
  {
    id: "atr-mobile-001",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "JPM momentum review",
    thesis:
      "JPM is showing improving momentum after a sector rotation, but the setup needs validation after costs and risk-budget impact.",
    ticker: "JPM",
    assetClass: "US equities",
    timeHorizon: "2-6 weeks",
    intendedExpression: "Long equity or sector-relative paper trade",
    status: "synthesis",
    decisionState: null,
    confidence: 58,
    trialCountImpact: 1,
    followUpDate: "2026-07-20",
    createdAt: now,
    claims: [
      {
        id: "claim-1",
        kind: "assumption",
        text: "Momentum persists after sector-relative transaction costs.",
        confidence: 61
      },
      {
        id: "claim-2",
        kind: "contradiction",
        text: "Signal may be a short-lived rotation rather than durable alpha.",
        confidence: 70
      }
    ],
    strongestCritique:
      "The setup is plausible but not yet decision-grade because signal robustness and portfolio overlap are under-specified.",
    disconfirmingTest:
      "Reject or mark needs more data if JPM fails to outperform the benchmark on financial-sector up days over the next five sessions.",
    historicalAnalogue: {
      title: "Sector rotation momentum review",
      similarity: "Prior bank momentum reviews depended on confirmation from breadth and benchmark-relative persistence.",
      differences: "This fallback sample has no live retrieval context and should not be treated as evidence.",
      resolution: "Treat the analogue as a placeholder until a live source map is available."
    },
    validation: {
      status: "specified",
      hypothesis: "JPM momentum can produce positive sector-relative forward returns after costs.",
      nullHypothesis: "The signal has no out-of-sample decision value after costs and benchmark exposure.",
      dataRequirements: ["Point-in-time prices", "Benchmark returns", "Cost model", "Liquidity filter"],
      protocol: "Walk-forward validation before promotion."
    },
    tradeability: [
      {
        topic: "Liquidity",
        question: "Can intended size be entered without unacceptable spread or slippage?",
        severity: "medium"
      }
    ],
    audit: [
      {
        id: "audit-1",
        timestamp: "09:30:00",
        eventType: "mobile.sample.loaded",
        detail: "Mobile fallback review loaded while API was unavailable."
      }
    ],
    sources: [
      {
        id: "source-1",
        title: "Mobile deterministic fallback",
        sourceType: "sample",
        timestamp: "2026-07-13",
        permission: "local_fixture",
        relevance: 0.2
      }
    ]
  },
  {
    id: "atr-mobile-002",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "SOXX breadth pullback",
    thesis:
      "Semiconductor breadth is deteriorating while headline index strength remains concentrated.",
    ticker: "SOXX",
    assetClass: "US equities",
    timeHorizon: "1-4 weeks",
    intendedExpression: "Watchlist and hedge review",
    status: "decision_recorded",
    decisionState: "watch",
    confidence: 64,
    trialCountImpact: 1,
    followUpDate: "2026-07-18",
    createdAt: "2026-07-06T13:05:00Z",
    claims: [
      {
        id: "claim-a",
        kind: "sourced",
        text: "Narrow leadership can make the index vulnerable to breadth reversal.",
        confidence: 68
      }
    ],
    strongestCritique:
      "Breadth weakness can persist for weeks in strong momentum regimes, so timing risk is high.",
    disconfirmingTest:
      "Defer if breadth stabilizes without price deterioration or volatility expansion.",
    historicalAnalogue: {
      title: "Semiconductor breadth divergence",
      similarity: "Earlier breadth reviews focused on whether index leadership narrowed before volatility expanded.",
      differences: "Fallback data lacks point-in-time holdings and constituent-level confirmation.",
      resolution: "Use as review scaffolding only; live web evidence remains authoritative."
    },
    validation: {
      status: "specified",
      hypothesis: "Breadth deterioration predicts weaker near-term semiconductor returns.",
      nullHypothesis: "Breadth deterioration adds no incremental information after trend and volatility.",
      dataRequirements: ["Constituent breadth", "Point-in-time holdings", "Benchmark returns"],
      protocol: "Panel test with cost and liquidity sensitivity."
    },
    tradeability: [
      {
        topic: "Expression",
        question: "Should the risk be expressed through options, sector ETF, or single-name hedge?",
        severity: "high"
      }
    ],
    audit: [
      {
        id: "audit-a",
        timestamp: "13:05:00",
        eventType: "decision.recorded",
        detail: "Human decision captured: watch."
      }
    ],
    sources: [
      {
        id: "source-a",
        title: "Mobile deterministic fallback",
        sourceType: "sample",
        timestamp: "2026-07-13",
        permission: "local_fixture",
        relevance: 0.2
      }
    ]
  }
];

export function buildSampleDataset(apiUrl: string): MobileDataset {
  return {
    source: "sample",
    apiUrl,
    loadedAt: new Date().toISOString(),
    health: {
      status: "offline-sample",
      service: "ambrosia-mobile-fallback",
      persistence: {
        mode: "sample"
      }
    },
    summary: {
      pendingReviews: sampleReviews.filter((review) => review.decisionState === null).length,
      decidedReviews: sampleReviews.filter((review) => review.decisionState !== null).length,
      activeSignals: 1,
      scannerCandidates: 2,
      alphaHypotheses: 1,
      priorityItems: 2
    },
    priorityQueue: [
      {
        kind: "review_decision",
        id: "atr-mobile-001",
        label: "JPM review awaits decision",
        severity: "warning",
        nextAction: "open_review"
      },
      {
        kind: "signal_readiness",
        id: "signal-mobile-jpm-momo",
        label: "JPM Momentum Up Signal needs evidence before action",
        severity: "warning",
        nextAction: "open_signal"
      }
    ],
    reviews: sampleReviews,
    scannerCandidates: [
      {
        ticker: "JPM",
        signal: "momentum_up",
        thesisSuggestion:
          "JPM is in a constructive momentum setup; create review before action because validation and risk budget remain open.",
        score: 0.82,
        price: 241.7,
        trend: "uptrend",
        rsi: 61,
        volume24h: 18400000,
        dataSource: "Mobile deterministic fallback",
        dataMode: "fallback",
        scannedAt: now
      },
      {
        ticker: "SOXX",
        signal: "mean_reversion_down",
        thesisSuggestion:
          "SOXX looks extended relative to recent breadth; route to adversarial review before hedging.",
        score: 0.74,
        price: 272.4,
        trend: "sideways",
        rsi: 68,
        volume24h: 9100000,
        dataSource: "Mobile deterministic fallback",
        dataMode: "fallback",
        scannedAt: now
      }
    ],
    signals: [
      {
        signalId: "signal-mobile-jpm-momo",
        name: "JPM Momentum Up Signal",
        status: "hypothesis",
        version: 1,
        universe: ["JPM"],
        horizon: "20d",
        formula: "close / close_20d - 1",
        benchmark: "SPY",
        costModel: "10 bps round-trip",
        latestDecisionState: "needs_more_data",
        latestDecisionAction: "HOLD",
        executionReadiness: "blocked_pending_evidence",
        linkedReviewCount: 1,
        outcomeState: "decision_unset",
        updatedAt: now
      }
    ],
    alphaHypotheses: [
      {
        hypothesisId: "alpha-mobile-breadth-001",
        title: "Semiconductor breadth deterioration",
        signalFamily: "breadth",
        thesis:
          "Weakening breadth inside semiconductor leadership may predict weaker short-horizon returns after costs.",
        universe: ["SOXX", "NVDA", "AMD", "AVGO"],
        horizon: "20d",
        status: "alpha_candidate",
        createdAt: now
      }
    ],
    enterpriseStatus: {
      schemaVersion: "mobile-enterprise-status.v1",
      status: "offline-sample",
      governance: {
        humanDecisionAuthority: true,
        llmInLiveOrderLoop: false,
        mobileFinalDecisionsRequireServerConfirmation: true
      }
    }
  };
}
