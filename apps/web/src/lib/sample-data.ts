import type { DashboardMetrics, TradeReview, DecisionPacket } from "./types";

export const sampleReviews: TradeReview[] = [
  {
    id: "atr-001",
    schemaVersion: "review.v1",
    workflowVersion: "adversarial-review.v1",
    title: "BTC miners lagging spot Bitcoin",
    thesis:
      "Bitcoin miners may be mispriced relative to spot Bitcoin after a sharp move in BTC that has not yet flowed through mining equities.",
    ticker: "MARA",
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
    ticker: "IWM",
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
    ticker: "TLT",
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

/**
 * Sample Decision Packets
 * Demonstrate the full quant workflow agent with market data, technicals, sentiment,
 * inter-market context, backtesting, risk, and multi-agent specialist outputs.
 */

export const samplePackets: DecisionPacket[] = [
  {
    id: "pkt-001",
    schemaVersion: "packet.v1",
    workflowVersion: "quant-agent.v1",
    title: "Tech rotation: NASDAQ 100 sell-off with risk parity trigger",
    thesis:
      "Large-cap tech is showing valuation and momentum exhaustion after a sustained rally. Risk parity flows may amplify a sell-off if volatility spikes. The setup offers a short via put spreads on QQQ.",
    ticker: "QQQ",
    assetClass: "US Equities - Large Cap",
    timeHorizon: "2-6 weeks",
    intendedExpression: "Short put spread: sell 380 puts, buy 360 puts",
    status: "decision_recorded",
    decisionState: "pursue",
    confidence: 71,
    trialCountImpact: 1,
    followUpDate: "2026-07-05",
    createdAt: "2026-06-24T09:30:00Z",
    claims: [
      {
        id: "claim-pkt1",
        kind: "sourced",
        text: "Valuation multiples have re-expanded despite slowing earnings growth.",
        evidence: "Earnings report and sentiment analysis",
        confidence: 78,
      },
      {
        id: "claim-pkt2",
        kind: "assumption",
        text: "Risk parity portfolios hold significant equity exposure tied to volatility levels.",
        confidence: 65,
      },
      {
        id: "claim-pkt3",
        kind: "contradiction",
        text: "Tech may remain well-bid if macro conditions continue to support growth narratives.",
        evidence: "Fed signaling and 10Y yields",
        confidence: 72,
      },
    ],
    strongestCritique:
      "The thesis depends on a valuation reset in a market that has been resilient to historical re-rating mechanisms. A short volatility expression is contra-consensus and may face crowd exits if realized.",
    disconfirmingTest:
      "Reject if QQQ rallies 5% on positive earnings surprises or if VIX fails to spike above 20 within two weeks of position entry.",
    historicalAnalogue: {
      title: "2021 growth rotation into value",
      similarity: "Tactical overvaluation in concentration with momentum exhaustion.",
      differences: "2021 saw Fed taper uncertainty; current macro backdrop differs.",
      resolution: "Rotation lasted 6-8 weeks with 15%+ drawdown in QQQ before stabilization.",
    },
    validation: {
      status: "specified",
      hypothesis: "QQQ underperforms SPY after valuation multiple expansion when momentum reverses.",
      nullHypothesis: "QQQ momentum is not predictively reversed by valuation metrics.",
      dataRequirements: [
        "Forward P/E history",
        "Earnings growth rates",
        "QQQ vs SPY relative returns",
        "Momentum indicators (RSI, MACD)",
      ],
      protocol: "Walk-forward validation with 252-day rolling window and rolling transaction costs.",
    },
    tradeability: [
      {
        topic: "Liquidity",
        question: "Can 10,000 contract spread be executed with sub-0.5 slippage?",
        severity: "high",
      },
      {
        topic: "Carry",
        question: "What is the weekly theta decay profile for ATM put spread?",
        severity: "medium",
      },
      {
        topic: "Exit",
        question: "At what stop-loss level (% of max risk) will we exit if thesis breaks?",
        severity: "high",
      },
    ],
    sources: [
      {
        id: "src-pkt1",
        title: "Q2 Tech Earnings Digest",
        sourceType: "user_note",
        timestamp: "2026-06-24",
        permission: "user_owned",
        relevance: 0.92,
      },
      {
        id: "src-pkt2",
        title: "Risk Parity Flow Analysis",
        sourceType: "prior_review",
        timestamp: "2026-06-18",
        permission: "user_owned",
        relevance: 0.87,
      },
    ],
    audit: [
      {
        id: "audit-pkt1",
        timestamp: "09:30:01",
        eventType: "intake.normalized",
        detail: "Thesis converted to packet.v1",
      },
      {
        id: "audit-pkt2",
        timestamp: "09:30:15",
        eventType: "market_data.fetched",
        detail: "Live QQQ snapshot and technicals retrieved",
      },
      {
        id: "audit-pkt3",
        timestamp: "09:30:45",
        eventType: "agents.completed",
        detail: "All 10 specialist agents completed output in 30s",
      },
      {
        id: "audit-pkt4",
        timestamp: "09:31:02",
        eventType: "decision.recorded",
        detail: "Human decision: pursue with put spread expression",
      },
    ],
    // Quant workflow agent fields
    marketSnapshot: {
      timestamp: "2026-06-24T09:30:00Z",
      price: 383.45,
      priceChange24h: 1.2,
      volume24h: 42500000,
      marketCap: 1850000000000,
      dataSource: "Yahoo Finance",
      dataSourceConfidence: "live",
    },
    technicals: {
      rsi: 68,
      rsiPeriod: 14,
      macdLine: 2.34,
      macdSignal: 1.89,
      macdHistogram: 0.45,
      movingAverage30: 378.12,
      movingAverage50: 375.58,
      movingAverage200: 365.23,
      volatilityRealized: 0.16,
      trend: "uptrend",
      updateTime: "2026-06-24T09:30:00Z",
      dataQuality: "verified",
    },
    sentiment: {
      overallScore: 62,
      sentiment: "neutral",
      newsScore: 58,
      socialScore: 65,
      trendDirection: "weakening",
      sources: ["NewsAPI", "Twitter Sentiment", "StockTwits"],
      lastUpdated: "2026-06-24T09:00:00Z",
      sourceConfidence: "verified",
    },
    interMarket: {
      correlationWithBenchmark: 0.92,
      correlationWithCommodities: -0.15,
      correlationWithBonds: -0.68,
      correlationWithDollar: -0.12,
      regimeState: "risk_on",
      spilloverRisk: "medium",
      notes: "Tech showing high correlation with SPY; bond volatility is elevated",
    },
    fundamentals: {
      earningsYield: 0.032,
      priceToBook: 8.5,
      debtToEquity: 0.45,
      roe: 0.28,
      growthRate: 0.08,
      qualityScore: 78,
      lastUpdated: "2026-06-21T00:00:00Z",
    },
    backtestPlan: {
      status: "eligible",
      entryRules: [
        "RSI > 65 and MACD histogram expanding",
        "Price > MA50 and MA200",
        "VIX < 20 (low complacency prerequisite)",
      ],
      exitRules: [
        "QQQ rallies 5% from entry (thesis break)",
        "Hold to 2-week expiration",
        "VIX spikes above 25 (flow trigger)",
      ],
      assumptions: [
        "Put spread priced at 0.85 debit",
        "Transaction costs: 0.02 per contract",
        "Liquidity available for 10k contracts",
      ],
      lookbackPeriod: 252,
      holdingPeriodDays: 14,
      riskConstraints: [
        "Max loss: 2% of portfolio",
        "Max position: 5% of ADV",
        "No correlation overlap with existing shorts",
      ],
    },
    backtestResult: {
      totalReturn: 0.18,
      sharpeRatio: 1.45,
      maxDrawdown: -0.08,
      winRate: 0.62,
      outOfSampleScore: 0.58,
      samplePeriod: "2024-01-01 to 2026-06-01",
      validityScore: "medium",
      hygienIssues: ["Backtest period includes 2-year low volatility regime", "Transaction costs not verified live"],
    },
    riskMonitor: {
      activePositionSize: 2100000,
      concentrationRisk: "medium",
      correlationOverlap: ["QQQ short hedge fund", "Tech sector short ETF"],
      varAtRisk: 0.035,
      maxDrawdownThreshold: 0.1,
      followUpTriggers: ["QQQ +5%", "VIX > 25", "Earnings surprise"],
      status: "monitoring",
    },
    portfolioContext: {
      grossExposure: 0.85,
      netExposure: 0.62,
      longExposure: 0.735,
      shortExposure: 0.115,
      concentrationBySector: { Technology: 0.35, Healthcare: 0.15, Financials: 0.12 },
      concentrationByFactor: { Growth: 0.42, Quality: 0.28, Momentum: 0.15 },
      relatedPositions: ["NVDA long", "MSFT long", "TSLA long"],
      factorOverlap: ["Growth factor underweight after this trade", "Momentum reversal protection"],
      riskBudgetRemaining: 0.15,
      sizingConstraints: ["Tech sector cannot exceed 40%", "Derivatives limited to 10% notional"],
    },
    confidenceBreakdown: {
      evidenceScore: 76,
      technicalScore: 73,
      sentimentScore: 62,
      interMarketScore: 68,
      validationScore: 58,
      tradeabilityScore: 82,
      riskAdjustedScore: 71,
      overallConfidence: 71,
      blockers: [],
      sourceProxyPenalties: 0,
    },
    agentOutputs: {
      marketData: {
        role: "Market Data",
        summary: "QQQ rallied 1.2% overnight; volume above average; liquidity strong",
        keyPoints: ["Price: $383.45", "Volume: 42.5M", "Market breadth weakening"],
        score: 78,
        timestamp: "2026-06-24T09:30:30Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      technical: {
        role: "Technical",
        summary: "RSI overbought, MACD histogram expanding but signal above line; uptrend intact",
        keyPoints: ["RSI 68 (overbought)", "MA alignment bullish", "Divergence warning"],
        score: 73,
        timestamp: "2026-06-24T09:30:45Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      sentiment: {
        role: "Sentiment",
        summary: "News sentiment cooling; social still positive but trend direction weakening",
        keyPoints: ["News: 58/100", "Social: 65/100", "Trend: weakening"],
        score: 62,
        timestamp: "2026-06-24T09:31:00Z",
        provider: "demo",
        fallbackUsed: true,
      },
      interMarket: {
        role: "Inter-Market",
        summary: "Risk-on regime, but bonds showing stress; correlation to SPY very high",
        keyPoints: [
          "Correlation (SPY): 0.92",
          "Correlation (Bonds): -0.68",
          "Regime: Risk-on / medium spillover",
        ],
        score: 68,
        timestamp: "2026-06-24T09:31:15Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      fundamental: {
        role: "Fundamental",
        summary: "Valuation has re-expanded; quality still strong but growth rate slowing",
        keyPoints: ["P/B: 8.5x", "ROE: 28%", "Growth: 8% (below historic avg)"],
        score: 64,
        timestamp: "2026-06-24T09:31:30Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      quant: {
        role: "Quant/Validation",
        summary: "Backtest shows 62% win rate over 252 days; Sharpe 1.45 but period was low vol",
        keyPoints: [
          "Win Rate: 62%",
          "Sharpe: 1.45",
          "Out-of-sample: 0.58 (medium confidence)",
        ],
        score: 58,
        timestamp: "2026-06-24T09:31:45Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      bull: {
        role: "Bull",
        summary: "Growth thesis intact; tech earnings remain strong; macro backdrop supportive",
        keyPoints: [
          "Tech earnings growing",
          "Fed supportive",
          "Institutional demand stable",
        ],
        score: 72,
        timestamp: "2026-06-24T09:32:00Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      bear: {
        role: "Bear",
        summary: "Valuation stretched; momentum exhausted; risk parity positioning heavy; correlation risk",
        keyPoints: ["P/E expanded 30%", "RSI 68 overbought", "Potential crowded short"],
        score: 74,
        timestamp: "2026-06-24T09:32:15Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      risk: {
        role: "Risk",
        summary: "Position size 2.1M notional, 2% max loss, VaR 3.5%; correlated with existing shorts",
        keyPoints: [
          "Max Loss: $42k (2%)",
          "Correlation overlap: 2 positions",
          "Liquidity: 10k contracts feasible",
        ],
        score: 78,
        timestamp: "2026-06-24T09:32:30Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
      pmSynthesis: {
        role: "PM Synthesis",
        summary:
          "Well-structured short thesis with medium confidence. Backtest hygiene medium. Risk controls clear. Decision: pursue via put spread.",
        keyPoints: [
          "Thesis: 71% confidence",
          "Risk: manageable, clear triggers",
          "Expression: put spread suitable",
        ],
        score: 71,
        timestamp: "2026-06-24T09:32:45Z",
        provider: "deterministic",
        fallbackUsed: false,
      },
    },
    coordinatorVersion: "coordinator.v1",
    providerInfo: {
      name: "Deterministic Multi-Agent Workflow",
      type: "deterministic",
      fallbackChain: ["local_ollama", "hosted_model", "demo"],
    },
  },
];