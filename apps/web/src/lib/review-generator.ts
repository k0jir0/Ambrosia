import type { ThesisInput, TradeReview } from "./types";

const now = () => new Date().toISOString();

export const thesisCandidates: ThesisInput[] = [
  {
    thesis:
      "Bitcoin miners may be lagging spot Bitcoin after a breakout, but the lag only matters if miner margins and liquidity confirm risk appetite rather than balance-sheet stress.",
    ticker: "MARA",
    assetClass: "Crypto-linked equities",
    timeHorizon: "1-4 weeks",
    intendedExpression: "Long liquid miner basket versus BTC proxy hedge",
    sourcePointer: "Generated candidate: BTC miner relative-strength watchlist"
  },
  {
    thesis:
      "Extended overnight trading may increase realized volatility in small-cap equities if off-hours liquidity fragments and next-session reversals become more frequent.",
    ticker: "IWM",
    assetClass: "Equities",
    timeHorizon: "4-12 weeks",
    intendedExpression: "Volatility screen before directional expression",
    sourcePointer: "Generated candidate: 24/6 trading market-structure monitor"
  },
  {
    thesis:
      "A crowded short in a thinly traded security may have poor asymmetry if borrow tightens before the catalyst resolves.",
    ticker: "SPCX",
    assetClass: "Equity",
    timeHorizon: "2-6 weeks",
    intendedExpression: "Short only if borrow, locate, spread, and exit liquidity support it",
    sourcePointer: "Generated candidate: borrow and squeeze-risk checklist"
  },
  {
    thesis:
      "A policy communication shift may support a curve-steepening watch if front-end repricing persists beyond the first reaction window.",
    ticker: "TLT",
    assetClass: "Rates",
    timeHorizon: "2-8 weeks",
    intendedExpression: "Paper review only until carry, roll, and liquidity are specified",
    sourcePointer: "Generated candidate: policy-event analogue queue"
  }
];

export function generateLocalReview(input: ThesisInput, currentTrialCount: number): TradeReview {
  const cleanThesis = input.thesis.trim() || "Untitled market thesis";
  const ticker = input.ticker.trim() || "Unspecified";
  const expression = input.intendedExpression.trim() || "Expression requires review before action";
  const lower = cleanThesis.toLowerCase();
  const expressionLower = expression.toLowerCase();
  const likelyNeedsRefusal =
    lower.includes("backtest") || lower.includes("alpha") || lower.includes("sharpe") || lower.includes("performance");
  const needsBorrowCheck = lower.includes("short") || lower.includes("borrow") || expressionLower.includes("short") || expressionLower.includes("borrow");

  return {
    id: `atr-local-${Date.now()}`,
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: ticker === "Unspecified" ? "New adversarial review" : `${ticker} adversarial review`,
    thesis: cleanThesis,
    ticker,
    assetClass: input.assetClass || "Unspecified",
    timeHorizon: input.timeHorizon || "Unspecified",
    intendedExpression: expression,
    status: "synthesis",
    decisionState: null,
    confidence: 52,
    trialCountImpact: currentTrialCount + 1,
    followUpDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    createdAt: now(),
    claims: [
      {
        id: "local-claim-1",
        kind: "assumption",
        text: "The thesis requires a clearly defined instrument, time horizon, and invalidation trigger before action.",
        confidence: 78
      },
      {
        id: "local-claim-2",
        kind: input.sourcePointer ? "sourced" : "unknown",
        text: input.sourcePointer
          ? "A user-provided source pointer is available but should be checked for permission, freshness, and relevance."
          : "No source pointer was attached, so current evidence is not yet grounded.",
        evidence: input.sourcePointer || undefined,
        confidence: input.sourcePointer ? 66 : 84
      },
      {
        id: "local-claim-3",
        kind: "inference",
        text: "The review should prioritize disconfirmation and tradeability before any performance estimate.",
        confidence: 74
      }
    ],
    strongestCritique:
      "The thesis may be directionally plausible but under-specified. Before it deserves capital or further research time, Ambrosia needs sharper evidence, a falsifiable disconfirming test, and proof that the intended expression is tradeable under realistic liquidity and transaction-cost assumptions.",
    disconfirmingTest:
      "Reject or mark needs more data if the proposed instrument does not respond to the thesis catalyst in the expected direction during the next relevant event window, or if the required data cannot be obtained point-in-time.",
    historicalAnalogue: {
      title: "Nearest analogue pending retrieval",
      similarity: "The system needs prior reviews or user notes to select a high-confidence analogue.",
      differences: "No retrieved analogue has been attached yet in the static MVP path.",
      resolution: "Treat this as an explicit retrieval gap rather than inventing a precedent."
    },
    validation: {
      status: likelyNeedsRefusal ? "refused" : "specified",
      hypothesis: cleanThesis,
      nullHypothesis: "The thesis contains no out-of-sample information after costs, liquidity, and multiple testing are considered.",
      dataRequirements: [
        "Point-in-time universe and instrument history",
        "Transaction-cost assumptions",
        "Liquidity and spread assumptions",
        "Multiple-testing budget",
        "Outcome label and follow-up horizon"
      ],
      protocol: "Generate validation specification first; do not report performance until hygiene requirements are satisfied.",
      refusalReason: likelyNeedsRefusal
        ? "Performance language detected. Refuse scoring until point-in-time data, transaction costs, liquidity, and trial budget are explicit."
        : undefined
    },
    tradeability: [
      { topic: "Liquidity", question: "Can the intended expression absorb the desired size without unacceptable spread or slippage?", severity: "high" },
      ...(needsBorrowCheck ? [{ topic: "Borrow", question: "Can the short be located, and is borrow cost stable enough for the thesis horizon?", severity: "high" } as const] : []),
      { topic: "Expression", question: `Is '${expression}' the cleanest way to express the thesis, or is there a better proxy?`, severity: "medium" },
      { topic: "Missing data", question: "Which market-structure data is unavailable and must be verified externally?", severity: "medium" }
    ],
    sources: [
      {
        id: "local-source-1",
        title: input.sourcePointer || "No source pointer attached",
        sourceType: input.sourcePointer ? "source_pointer" : "missing_source",
        timestamp: now().slice(0, 10),
        permission: input.sourcePointer ? "pointer_only" : "user_owned",
        relevance: input.sourcePointer ? 0.68 : 0.2
      }
    ],
    audit: [
      { id: "local-audit-1", timestamp: new Date().toLocaleTimeString(), eventType: "intake.normalized", detail: "Local deterministic review generated" },
      { id: "local-audit-2", timestamp: new Date().toLocaleTimeString(), eventType: "validation.checked", detail: likelyNeedsRefusal ? "Refusal path selected" : "Validation specification path selected" }
    ]
  };
}
