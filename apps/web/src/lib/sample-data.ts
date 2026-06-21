import type { DashboardMetrics, TradeReview } from "./types";

export const sampleReviews: TradeReview[] = [
  {
    id: "atr-001",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "BTC miners lagging spot Bitcoin",
    thesis:
      "Bitcoin miners may be mispriced relative to spot Bitcoin after a sharp move in BTC that has not yet flowed through mining equities.",
    ticker: "BTC / miners",
    assetClass: "Crypto-linked equities",
    timeHorizon: "1-4 weeks",
    intendedExpression: "Long basket of liquid BTC miners versus BTC proxy hedge",
    status: "decision_recorded",
    decisionState: "watch",
    confidence: 62,
    trialCountImpact: 1,
    followUpDate: "2026-06-28",
    createdAt: "2026-06-21T15:14:00Z",
    claims: [
      {
        id: "claim-1",
        kind: "sourced",
        text: "The thesis depends on miners catching up to BTC rather than BTC mean-reverting first.",
        evidence: "User watchlist and prior miner/BTC review pointer",
        confidence: 72
      },
      {
        id: "claim-2",
        kind: "assumption",
        text: "Equity beta to BTC remains stable over the next one to four weeks.",
        confidence: 55
      },
      {
        id: "claim-3",
        kind: "contradiction",
        text: "Miners may be lagging because hash-price pressure or balance-sheet risk is being repriced.",
        evidence: "Prior review objection: miners underperform in margin compression regimes",
        confidence: 68
      }
    ],
    strongestCritique:
      "The lag may not be inefficiency. It may be the market discounting miner-specific operating leverage, financing needs, or post-halving economics. A long-miners expression could be a levered balance-sheet trade, not a clean BTC catch-up trade.",
    disconfirmingTest:
      "Reject or defer if the most liquid miner basket fails to outperform BTC on up-days while underperforming on flat/down BTC days over the next five sessions.",
    historicalAnalogue: {
      title: "Miner beta compression after prior BTC impulse moves",
      similarity: "BTC moved first while miner equities initially lagged.",
      differences: "Financing conditions and mining economics differ materially by cycle.",
      resolution:
        "Lag resolved only when BTC strength persisted and miner margins improved; otherwise lag correctly signaled equity-specific stress."
    },
    validation: {
      status: "refused",
      hypothesis: "Miner basket outperforms BTC proxy after BTC breakout when miner lag exceeds threshold.",
      nullHypothesis: "Miner lag contains no positive forward relative-return information.",
      dataRequirements: [
        "Point-in-time miner universe",
        "Corporate actions and survivorship controls",
        "BTC proxy returns aligned to equity market hours",
        "Transaction cost and liquidity assumptions"
      ],
      protocol: "Walk-forward validation with multiple-testing budget before scoring.",
      refusalReason:
        "Do not report performance until point-in-time miner universe and transaction assumptions are specified."
    },
    tradeability: [
      { topic: "Liquidity", question: "Which miner names can absorb intended size without crossing wide spreads?", severity: "high" },
      { topic: "Expression", question: "Is the thesis better expressed through a basket, ETF proxy, or options structure?", severity: "medium" },
      { topic: "Volatility", question: "Does implied volatility already price the catch-up move?", severity: "medium" }
    ],
    sources: [
      {
        id: "src-1",
        title: "User watchlist: BTC miners relative strength",
        sourceType: "user_note",
        timestamp: "2026-06-21",
        permission: "user_owned",
        relevance: 0.91
      },
      {
        id: "src-2",
        title: "Prior review: miner lag regimes",
        sourceType: "prior_review",
        timestamp: "2026-06-12",
        permission: "user_owned",
        relevance: 0.86
      }
    ],
    audit: [
      { id: "audit-1", timestamp: "15:14:01", eventType: "intake.normalized", detail: "Thesis converted to review.v1" },
      { id: "audit-2", timestamp: "15:14:03", eventType: "retrieval.hybrid", detail: "2 source pointers selected" },
      { id: "audit-3", timestamp: "15:14:08", eventType: "validation.refused", detail: "Point-in-time universe missing" }
    ]
  },
  {
    id: "atr-002",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "24/6 trading and small-cap volatility",
    thesis:
      "Extended overnight trading may increase volatility and gap risk in small-cap equities as liquidity fragments outside core hours.",
    ticker: "IWM / small caps",
    assetClass: "Equities",
    timeHorizon: "1-3 months",
    intendedExpression: "Watchlist and volatility screen before directional trade",
    status: "decision_recorded",
    decisionState: "needs_more_data",
    confidence: 48,
    trialCountImpact: 1,
    followUpDate: "2026-07-05",
    createdAt: "2026-06-20T18:40:00Z",
    claims: [
      { id: "claim-a", kind: "assumption", text: "Overnight participation is large enough to alter realized volatility.", confidence: 42 },
      { id: "claim-b", kind: "unknown", text: "Venue-level depth and off-hours order book quality are not available yet.", confidence: 80 },
      { id: "claim-c", kind: "sourced", text: "Prior notes suggest liquidity gaps matter more for small caps than mega caps.", evidence: "Market structure note pointer", confidence: 64 }
    ],
    strongestCritique:
      "The thesis may be directionally plausible but too broad. Without venue-level depth, order types, participation, and realized spread data, the review can only define monitoring criteria rather than support a trade.",
    disconfirmingTest:
      "Reject the thesis if off-hours volume grows without any increase in open-to-close volatility, spread proxies, or next-session reversal behavior in the monitored universe.",
    historicalAnalogue: {
      title: "Extended-hours liquidity episodes in retail-heavy equities",
      similarity: "Thin liquidity outside core hours amplified single-name moves.",
      differences: "24/6 market structure and participant mix may differ from episodic extended-hours trading.",
      resolution: "Impact was concentrated in less liquid names and decayed when liquidity normalized."
    },
    validation: {
      status: "specified",
      hypothesis: "Small caps with high off-hours participation show higher next-session realized volatility.",
      nullHypothesis: "Off-hours participation does not predict next-session realized volatility after controlling for baseline liquidity.",
      dataRequirements: ["Off-hours volume", "Core-hours volume", "Spread proxy", "Realized volatility", "Point-in-time small-cap universe"],
      protocol: "Walk-forward panel test with transaction-cost and liquidity filters."
    },
    tradeability: [
      { topic: "Data", question: "Which source supplies reliable off-hours volume and spread proxies?", severity: "high" },
      { topic: "Universe", question: "What liquidity floor excludes names that cannot be traded responsibly?", severity: "high" },
      { topic: "Expression", question: "Is the first expression a screen, options basket, or volatility proxy?", severity: "medium" }
    ],
    sources: [
      { id: "src-a", title: "Market structure note: small-cap off-hours liquidity", sourceType: "user_note", timestamp: "2026-06-18", permission: "user_owned", relevance: 0.88 }
    ],
    audit: [
      { id: "audit-a", timestamp: "18:40:02", eventType: "intake.normalized", detail: "Thesis classified as market-structure review" },
      { id: "audit-b", timestamp: "18:40:08", eventType: "validation.specified", detail: "Monitoring validation defined without performance scoring" }
    ]
  },
  {
    id: "atr-003",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "Curve steepener after policy shift",
    thesis: "A policy shift may make a curve-steepening expression attractive if front-end rates reprice faster than long-end growth expectations.",
    ticker: "Rates curve",
    assetClass: "Rates",
    timeHorizon: "2-8 weeks",
    intendedExpression: "Paper review only; no execution in MVP",
    status: "synthesis",
    decisionState: null,
    confidence: 57,
    trialCountImpact: 1,
    followUpDate: "2026-06-30",
    createdAt: "2026-06-19T13:05:00Z",
    claims: [
      { id: "claim-r1", kind: "sourced", text: "The idea depends on policy communication changing front-end expectations.", evidence: "Policy note pointer", confidence: 67 },
      { id: "claim-r2", kind: "assumption", text: "Long-end inflation premium does not fall enough to offset front-end repricing.", confidence: 51 }
    ],
    strongestCritique: "The curve may already reflect the policy path, and a steepener could be a crowded expression with poor asymmetry after the first repricing move.",
    disconfirmingTest: "Defer if the curve fails to steepen on policy-sensitive front-end rallies or if positioning data shows the steepener is already crowded.",
    historicalAnalogue: {
      title: "Post-policy communication curve repricing",
      similarity: "Front-end led the initial reaction.",
      differences: "Inflation regime and issuance backdrop differ.",
      resolution: "Trades worked only when policy surprise persisted beyond the first reaction window."
    },
    validation: {
      status: "refused",
      hypothesis: "Policy-shift events predict curve steepening over 2-8 weeks.",
      nullHypothesis: "Policy-shift labels have no out-of-sample curve-steepening information.",
      dataRequirements: ["Point-in-time event labels", "Curve history", "Transaction-cost assumptions", "Positioning proxy"],
      protocol: "Event-study specification required before scoring.",
      refusalReason: "Event labels are not defined tightly enough for a backtest."
    },
    tradeability: [
      { topic: "Expression", question: "Which curve points express the thesis with acceptable roll and carry?", severity: "high" },
      { topic: "Crowding", question: "What proxy indicates steepener positioning is not already saturated?", severity: "medium" }
    ],
    sources: [
      { id: "src-r1", title: "Policy communication note", sourceType: "source_pointer", timestamp: "2026-06-19", permission: "pointer_only", relevance: 0.82 }
    ],
    audit: [
      { id: "audit-r1", timestamp: "13:05:03", eventType: "validation.refused", detail: "Event labels under-specified" }
    ]
  }
];

export const dashboardMetrics: DashboardMetrics = {
  reviewsCreated: 38,
  rejectedOrDeferred: 17,
  followUpsRecorded: 11,
  averageConfidence: 56,
  activeTrialCount: 38
};