# Ambrosia Quant Workflow Agent — Pitch Deck Outline

> [!WARNING]
> Historical draft; not approved for investors or diligence. URLs, traction,
> performance, security, and completion statements are unverified. Use the
> Index132 claims register and implementation ledger.

**Date**: 2026-06-24  
**Product**: Ambrosia  
**Status**: End-of-Day-1 Prototype

---

## Slide 1: Cover

**Ambrosia**

*The Quant Workflow Agent for Pre-Trade Decision Discipline*

Structured review, multi-dimensional validation, and auditable decision-making for professional traders and PMs.

---

## Slide 2: The Problem

**Why Investment Workflows Fail**

- ❌ Thesis generation without validation
- ❌ Decision-making is scattered (email, notes, conversations)
- ❌ No systematic challenge to assumptions
- ❌ Audit trail is weak or nonexistent
- ❌ Risk monitoring is reactive, not proactive
- ❌ Technology is optimized for idea capture, not idea rejection

**Result**: Costly mistakes, poor reproducibility, regulatory friction.

---

## Slide 3: The Solution

**Ambrosia: A Structured Decision Engine**

Ambrosia turns a raw thesis into a comprehensive decision packet by integrating:

- **Market Data**: Real-time or deterministic market snapshots
- **Technicals**: RSI, MACD, moving averages, volatility, trend
- **Sentiment**: News, social, and consensus signals
- **Inter-Market**: Correlation, spillover risk, regime analysis
- **Fundamentals**: Valuation, growth, quality metrics
- **Specialist Agents**: 10 parallel agents (market data, technical, sentiment, fundamental, quant, bull, bear, risk, PM synthesis)
- **Backtesting**: Controlled validation with eligibility gates
- **Risk Monitoring**: Real-time position and portfolio alerts
- **Audit Trail**: Complete decision record with provenance

**Result**: Disciplined, repeatable, auditable investment decisions.

---

## Slide 4: The Decision Packet

**13 Structured Sections**

| Section | Purpose |
|---------|---------|
| **Signal** | Thesis, timeframe, intended expression |
| **Market Snapshot** | Price, volume, volatility, data provenance |
| **Technicals** | RSI, MACD, MAs, trend, realized vol |
| **Sentiment** | News, social, consensus direction |
| **Inter-Market** | Correlations, regime, spillover risk |
| **Fundamentals** | Valuation, growth, quality, earnings |
| **Bull/Bear Debate** | Thesis support vs. disconfirming test |
| **Validation/Backtest** | Historical performance with hygiene gates |
| **Risk** | Position sizing, concentration, VaR, triggers |
| **Confidence** | Evidence, technical, sentiment, validation scores |
| **Decision** | Pursue, watch, reject, needs more data |
| **Audit** | Complete timestamp and provenance log |
| **Follow-Up** | Trigger conditions and schedule |

---

## Slide 5: Common Actions

**One-Click Access to Core Workflow**

- **New Packet**: Create a fresh decision packet
- **Generate Thesis**: AI-assisted thesis starter
- **Ingest Alert**: TradingView or manual signal intake
- **Refresh Metrics**: Update market data and indicators
- **View Technicals**: Full technical analysis dashboard
- **View Sentiment**: Market and news sentiment breakdown
- **Compare Markets**: Inter-market and correlation analysis
- **Prepare Backtest**: Define entry/exit rules and assumptions
- **Run Backtest**: Execute controlled test if eligible
- **Record Decision**: Capture final decision and reasoning
- **Set Follow-Up**: Schedule next review or trigger condition
- **View Risks**: Active risk dashboard and alerts
- **Export Report**: Generate PDF or markdown decision report

---

## Slide 6: The Multi-Agent Architecture

**10 Specialist Roles, Parallel Execution**

```
┌─────────────────────────────────────────────────────────┐
│                    Coordinator                          │
│         Routes packet to all specialists in parallel    │
└──────────────────┬──────────────────────────────────────┘
         ┌─────────┼─────────┬──────────┐
         │         │         │          │
    ┌────▼───┐  ┌──▼──┐  ┌──▼──┐   ┌──▼──┐
    │ Market │  │Tech │  │Sent │   │Inter│
    │ Data   │  │     │  │iment│   │Mkt  │
    └────────┘  └─────┘  └─────┘   └─────┘
         │         │         │          │
    ┌────▼───┐  ┌──▼──┐  ┌──▼──┐   ┌──▼──┐
    │Funda-  │  │Quant│  │Bull │   │Bear │
    │mental  │  │     │  │     │   │     │
    └────────┘  └─────┘  └─────┘   └─────┘
         │         │         │          │
         │    ┌────▼────┐    │          │
         │    │  Risk   │    │          │
         │    └────┬────┘    │          │
         └────────┬──────────┴──────────┘
                  │
          ┌───────▼────────┐
          │  PM Synthesis  │
          │  (Final Score) │
          └────────────────┘
```

**Each agent outputs**:
- Structured summary
- Key points and insights
- Numeric score (0-100)
- Confidence and source metadata

---

## Slide 7: Confidence Scoring

**Multi-Factor Confidence Model**

Confidence is not model-only. It's a weighted blend of:

| Component | Weight | Notes |
|-----------|--------|-------|
| **Evidence** | 20% | Sourced claims vs. assumptions |
| **Technical** | 15% | Signal strength, pattern fit |
| **Sentiment** | 15% | News, social, consensus alignment |
| **Inter-Market** | 10% | Correlation, spillover risk |
| **Validation** | 15% | Backtest results, out-of-sample score |
| **Tradeability** | 10% | Liquidity, execution, carry |
| **Risk-Adjusted** | 15% | Sharpe, max drawdown, Kelly fit |

**Transparency**: Each component is visible, scored, and traceable to sources.

---

## Slide 8: Backtesting with Guardrails

**No Fake Performance Claims**

Ambrosia enforces strict hygiene gates:

- ✅ Entry/exit rules must be precisely defined
- ✅ Assumptions (costs, liquidity, slippage) must be explicit
- ✅ Lookback period ≥ 252 trading days
- ✅ Out-of-sample verification required
- ✅ Transaction costs included
- ✅ Survivorship bias controlled where possible
- ✅ Refusal if gates cannot be met

**Result**: Only credible backtests are reported. Refusals are explicit.

---

## Slide 9: Risk Monitoring

**Real-Time Alerts and Triggers**

Every packet includes a risk monitor:

- **Active Position Size**: Notional and % of portfolio
- **Concentration Risk**: Sector, factor, instrument overlap
- **VaR / Max Drawdown**: Tail risk monitoring
- **Correlation Overlap**: Identify hidden factor bets
- **Follow-Up Triggers**: Automatic re-review conditions
- **Status Dashboard**: Monitor → Alert → Safe states

**Alert Examples**:
- Position moves ±5%
- VIX spikes above threshold
- Correlated short position triggers stop loss
- Earnings or catalyst date arrives

---

## Slide 10: Portfolio Context

**Situate Every Trade in Full Context**

Every decision packet includes:

- **Gross and Net Exposure**: Total portfolio risk
- **Concentration by Sector and Factor**: Identify crowding
- **Related Positions**: Understand factor overlap and hedges
- **Risk Budget Remaining**: Enforce portfolio constraints
- **Sizing Constraints**: Asset class and strategy limits

**Human Authority**: No live order execution. All trading remains advisor mode.

---

## Slide 11: Data Provenance & Fallback Strategy

**Honest About Data Sourcing**

- Every metric is labeled with data source
- Live data is marked as "live", fallback data as "fallback" or "demo"
- If a data source becomes unavailable, a deterministic fallback activates
- Fallback is clearly marked in UI and audit trail
- No hidden model dependencies; no fake data

**Example Fallback Chain**:
1. Live Yahoo Finance or Polygon API
2. If unavailable → Deterministic synthetic data with CSV history
3. If that fails → Demo mode with realistic sample patterns
4. User is always informed via status indicator and audit log

---

## Slide 12: Privacy & Control

**Your Data, Your Rules**

- On-premises deployment option with PostgreSQL persistence
- No third-party dependency for core decision logic
- API-backed market data is optional; demo mode works offline
- LLM provider is pluggable (local Ollama, OpenAI, Anthropic, or demo)
- Audit trail never leaves your systems
- Decision packets are your intellectual property

---

## Slide 13: Evaluation & Governance

**Measurement and Validation**

Day 1 metrics (extensible):

- **Packet Speed**: Median time to complete all specialist agents
- **Confidence Calibration**: Do packets with 70% confidence actually succeed 70% of the time?
- **Backtest Hygiene**: % of backtests that pass gate checks
- **Refusal Accuracy**: % of refused backtests that would have been invalid
- **Risk Alert Precision**: % of alerts that precede actual P&L events

---

## Slide 14: The North Star

**By End of Day 7, Ambrosia Will Be**:

✅ A coherent quant workflow agent with 13-section decision packets  
✅ Backed by 10 specialist agents in parallel  
✅ Integrated with real or deterministic market data and technicals  
✅ Enforcing backtest gates with explicit refusals  
✅ Recording complete audit trails  
✅ Managing portfolio context and risk monitoring  
✅ Supporting multi-factor confidence scoring  
✅ Testable against evaluation fixtures  
✅ Presentable to investors and traders  
✅ Durable (PostgreSQL-backed) and fallback-resilient  

**Non-Negotiables**:
- ❌ No fake live data
- ❌ No hidden provenance
- ❌ No model-only confidence
- ❌ No unbounded autonomy
- ❌ No live execution
- ❌ No broker mutations

---

## Slide 15: Go-to-Market

**Phase 1: MVP Private Beta (Month 1-2)**
- Onboard 5-10 professional traders and PMs
- Collect feedback on packet UX, agent outputs, and risk alerting
- Gather performance attribution data for calibration
- Build case studies for regulatory and compliance teams

**Phase 2: Hosted Multi-Tenant (Month 3-6)**
- Deploy on Render or dedicated cloud infrastructure
- Add user authentication and permission tiers
- Enable multi-user review workflows and approvals
- Launch API access for third-party integrations

**Phase 3: Advanced Features (Month 6-12)**
- Live broker connectivity (Sandbox first, then live)
- Factor attribution and scenario analysis
- Custom backtesting with alternative data sources
- Collaborative workflows (peer review, compliance audit)

---

## Slide 16: Competitive Advantage

**Why Ambrosia Is Different**

| Dimension | Ambrosia | Competitors |
|-----------|----------|-------------|
| **Specialist Agents** | 10 parallel roles | Generic LLM or none |
| **Backtest Gates** | Strict hygiene, explicit refusals | No guardrails |
| **Risk Monitoring** | Continuous, portfolio-aware | Manual or ad hoc |
| **Audit Trail** | Complete, immutable | Scattered or missing |
| **Data Honesty** | Fallback strategy, transparent sources | Opaque or overfit |
| **Confidence** | Multi-factor, evidence-based | Model-only or heuristic |
| **Human Authority** | Explicit decision point, no autonomy | Blurred or autonomous |

---

## Slide 17: Team & Roadmap

**Execution Model**

- **Product/UI Lead**: Owns packet UX, common actions, graphs, demo
- **Backend/Data Lead**: Owns persistence, schemas, adapters, audit
- **Agent/Model Lead**: Owns provider abstraction, specialist roles, coordination
- **Quant/Backtest Lead**: Owns indicators, validation gates, evaluation
- **Risk/Evaluation Lead**: Owns risk monitoring, outcome attribution, testing

**Roadmap Phases**:
- **Days 1-7**: Product surface, durable memory, market data, technicals, sentiment, alerts, providers, agents, backtesting, risk, portfolio context, evaluation, pitch, demo
- **Month 2**: Live broker sandbox, factor attribution, advanced sentiment
- **Month 3+**: Multi-tenant SaaS, collaborative workflows, custom backtesting, dark pool integration

---

## Slide 18: Investment Thesis

**The Opportunity**

- **TAM**: $500B+ professional investment management industry
- **Problem**: Traders and PMs lack systematic pre-trade validation
- **Solution**: Ambrosia embeds discipline and auditability into workflow
- **Unit Economics**: Per-user subscription or per-trade fee
- **Margin**: 70-80% gross margin on cloud infrastructure
- **Growth**: 10x market concentration by targeting top 1% of hedge funds, asset managers, and prop traders

---

## Slide 19: Use Cases

### Use Case 1: Hedge Fund Risk Committee

*Weekly review of top signal candidates before allocation.*

- Packet flow: Idea → multi-agent analysis → risk review → allocation decision
- Backtest gates prevent overfitted strategies
- Audit trail supports regulatory review
- Outcome tracking for compensation/performance tiers

### Use Case 2: Prop Trading Desk

*Intraday thesis intake from TradingView alerts or manual research.*

- Alert → Packet creation → Quick market/tech/sentiment check → Decision
- Risk monitoring on all open positions
- Follow-up triggers when thesis breaks
- Example: "Short tech on RSI >70 and negative sentiment divergence"

### Use Case 3: Institutional Asset Manager

*Overnight thesis research becomes structured packet.*

- Research team inputs thesis
- Packet routed to market data, fundamental, quant agents
- Portfolio manager receives confidence-scored recommendation
- Decision packet goes to compliance for audit

---

## Slide 20: Financial Projections (Outline)

### Year 1
- Beta customers: 10 trading desks
- Revenue: $500k (mix of SaaS and consulting)
- Operating burn: $1.2M (4 FTE + infrastructure)

### Year 2
- Paying customers: 50-100
- Revenue: $3M+
- Gross margin: 70%
- Operating margin: -20% (still building product)

### Year 3
- Market presence in top 10% of buy-side
- Revenue: $10M+
- Gross margin: 75%
- Operating margin: 0% (break-even or positive)

---

## Slide 21: Ask

**$2M Seed Funding**

- **Use of Funds**:
  - Team expansion: 5-7 FTE (18 months runway)
  - Infrastructure: Cloud, data, compliance
  - Customer acquisition and support
  - Sales and marketing

- **Expected Outcomes**:
  - 50+ paying customers by end of Year 1
  - $3M+ ARR by end of Year 2
  - Profitable by Year 3

- **Exit Strategy**:
  - Strategic acquisition by Bloomberg, Refinitiv, FactSet, or major broker
  - Or independent SaaS player with multi-hundred-million-dollar valuation

---

## Slide 22: Closing

**Ambrosia**

*Investment discipline at scale.*

- Discipline: Multi-dimensional validation before capital is committed
- Scale: 10 parallel specialist agents, auditable workflows
- Trust: Transparent data sources, explicit refusals, complete audit trail
- Adoption: Integrated into existing trading desks and PM workflows

**Contact**

- Website: [to-be-determined]
- Email: [to-be-determined]
- Demo: [Live at https://ambrosia-5aec.onrender.com/]

---

## Appendix A: Technical Architecture (If Needed)

**Frontend**:
- Next.js workbench with real-time packet updates
- TypeScript type safety across decision packet structure
- Tailwind CSS with dark-mode-first design

**Backend**:
- FastAPI Python service with deterministic and LLM-backed paths
- PostgreSQL with pgvector for hybrid retrieval
- Model provider abstraction supporting Ollama, OpenAI, Anthropic, or demo

**Integration Points**:
- TradingView webhooks for alert intake
- Market data APIs (Yahoo, Polygon, IEX, or synthetic)
- Sentiment APIs (NewsAPI, Twitter, StockTwits)
- Backtest execution (zipline or custom engine)
- Broker APIs (for future live execution)

---

## Appendix B: Sample Decision Packet

**[Include screenshot or live demo of a completed packet with all 13 sections filled]**

Example: "Tech rotation short via QQQ put spread"

- Thesis: Value exhaustion + risk parity pressure
- Market snapshot: $383.45, +1.2% vol
- Technicals: RSI 68, MACD bullish but overbought
- Sentiment: Cooling, trend weakening
- Inter-market: Risk-on regime, high bonds correlation
- Bull: Tech earnings still solid, Fed supportive
- Bear: Valuation stretched, momentum peaked
- Backtest: 62% win rate, Sharpe 1.45, eligible
- Risk: $2.1M position, 2% max loss
- Confidence: 71% overall
- Decision: Pursue via put spread
- Follow-ups: Trigger on QQQ +5% or VIX >25

---

## Appendix C: Evaluation Metrics

### Operational Metrics
- **Packet generation time**: Median time from idea to final score
- **Agent latency**: Time per specialist role to complete
- **Fallback activation**: Frequency of data source failover

### Quality Metrics
- **Confidence calibration**: Do 70% confidence packets actually succeed 70% of the time?
- **Backtest hygiene**: % of backtests that pass gate checks
- **Refusal accuracy**: % of refused backtests that would have failed out-of-sample

### Adoption Metrics
- **Active users**: Traders and PMs using the product weekly
- **Packet volume**: Decisions being made through Ambrosia
- **Outcome attribution**: % of trades traced back to Ambrosia packets

---

**End of Pitch Deck Outline**

*For live demo and screenshots, see the Ambrosia MVP running at https://ambrosia-5aec.onrender.com/*
