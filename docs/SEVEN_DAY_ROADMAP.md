# Ambrosia Seven-Day Hardcore Completion Roadmap

Compressing The 90-Day Quant Workflow Agent Roadmap Into A 7-Day Full-Scope Build

**Date**: 2026-06-24

---

## 1. Purpose

This document defines the new execution scope:

**Finish the Ambrosia quant workflow agent in 7 days.**

The scope is not reduced.

The 7-day goal is to accomplish the full Index 29 roadmap at maximum practical speed:
decision-packet UI, common actions, durable memory, retrieval, market metrics,
technical indicators, TradingView alert workflow, LLM/Ollama/provider layer, MCP-style
tool boundaries, coordinator and specialist agents, backtest gates, controlled
backtesting, risk monitoring, portfolio context, evaluation, private-beta demo, and a
presentable finished-product pitch deck.

### Index 33 Influence (Investor Alignment Overlay)

This roadmap keeps the original quant workflow north star and core execution sequence,
while incorporating investor-language influence from Index 33:

- Ambrosia should be externally framed as agent-native trading for financial decisioning.
- Ambrosia should be communicated as a platform with three integrated product surfaces:
  - Agentic AI for Investments / Investment Trading Decisions (Decisions)
  - Swarm Private
  - Enterprise Agentic Swarm Marketplace
- This is a narrative and packaging overlay, not a replacement of the core technical
  roadmap in this document.
- Product claims in deck/demo/docs must match what is implemented in-app.

### The Attitude Is Hardcore:

- build the vertical product end to end;
- stub only when a dependency is external and unavailable;
- label every stub honestly;
- wire the architecture so stubs can be replaced;
- prioritize working software over theoretical completeness;
- keep the UI extremely user friendly;
- keep human decision authority explicit;
- do not ship fake market claims;
- do not reduce the north star.

---

## 2. Definition Of Seven-Day Done

By the end of Day 7, Ambrosia should have:

### 2.1 Product Identity

Ambrosia is clearly presented as a quant workflow agent.

### 2.2 Decision-Packet UI

A complete, pitchdeck-style packet interface with sections for:
- Signal/thesis
- Market snapshot
- Technicals
- Sentiment
- Inter-market analysis
- Fundamentals
- Bull/bear debate
- Validation/backtesting
- Risk monitor
- Confidence
- Decision
- Audit
- Follow-up

### 2.3 Common Actions

Common trader/PM actions are surfaced in persistent controls:
- New packet
- Generate thesis
- Ingest alert
- Refresh metrics
- View technicals
- View sentiment
- Compare markets
- Prepare backtest
- Run eligible backtest
- Record decision
- Set follow-up
- View risks
- Export report

### 2.4 Quant/Trader Graphs

Verifiable graphs familiar to quants and traders:
- Price plus moving averages
- RSI
- MACD or trend state
- Realized volatility
- Volume
- Drawdown
- Correlation/beta where data exists
- Confidence components
- Risk status
- Decision/outcome distribution

### 2.5 Durable Memory

PostgreSQL-backed:
- Reviews
- Packets
- Decisions
- Sources
- Audit events
- Workflow runs
- Metric snapshots
- Model/tool call records
- Risk monitors
- Outcomes

### 2.6 Retrieval

Hybrid retrieval over:
- Prior reviews
- Notes
- Sources
- Packet artifacts
- With retrieval audit

### 2.7 Market Data

A market-data adapter layer with:
- At least one working data path
- One deterministic fallback path

### 2.8 Technical Metrics

- RSI
- 30/50-day moving averages
- Volatility
- Volume
- Trend
- Proxy/missing-data handling

### 2.9 Sentiment

Sentiment section and adapter boundary, with:
- At least one working source if available
- OR clearly labeled deterministic/demo source if not

### 2.10 TradingView

Hardened alert-to-packet intake with:
- Provenance
- Prompt-injection protection
- Signal queue

### 2.11 LLM/Ollama/Provider Layer

Model-provider abstraction supporting:
- Deterministic fallback
- Local Ollama where available
- Hosted model where credentials are available
- Hybrid mode

### 2.12 MCP-Style Tool Boundary

Tool interfaces for:
- Market data
- Retrieval
- Technicals
- Sentiment
- Backtesting
- Report export
- Risk monitoring

*Note: If actual MCP serverization is too slow, ship MCP-compatible internal boundaries with explicit next-step serverization.*

### 2.13 Agent Coordinator

Coordinator workflow that routes to specialist roles.

### 2.14 Specialist Agents

With structured outputs for:
- Market data
- Technical
- Sentiment/news
- Inter-market
- Fundamental
- Quant/validation
- Bull
- Bear
- Risk
- PM synthesis

### 2.15 Backtesting

- Backtest_plan schema
- Eligibility gates
- Refusal states
- At least one controlled backtest path for a narrow valid case

### 2.16 Risk Monitoring

- Risk monitor objects
- Active risk dashboard
- Follow-up triggers
- Reopened packet state

### 2.17 Portfolio Context

- Exposure
- Concentration
- Related positions
- Factor overlap
- Risk budget
- Sizing constraint fields
- *No live broker execution*

### 2.18 Confidence Derivation

Evidence, technical, sentiment, inter-market, validation, tradeability,
risk-adjusted, and overall confidence with:
- Blockers
- Source/proxy penalties

### 2.19 Evaluation

- Tests
- Eval fixtures
- Provider ablations where possible
- Workflow-speed metrics
- Unsupported-claim checks
- Invalid-backtest checks
- Graph verification

### 2.20 Pitch Deck

A presentable finished-product pitch deck outline or markdown deck with:
- Screenshots or screenshot placeholders

### 2.21 Demo

A coherent investor/private-beta demo that matches:
- Product narrative
- Deck narrative

### 2.22 Investor-Language Consistency

The external investor narrative should be demonstrably supported by the product:
- Decisions is represented by the decision-packet workflow
- Swarm Private is represented by specialist routing and structured role outputs
- Enterprise Marketplace is represented by governance/tool-boundary scaffolding and
  clear next-step serverization path

---

## 3. Non-Negotiables

Do not compromise these:

- ❌ No fake live data
- ❌ No hidden data provenance
- ❌ No model-only confidence
- ❌ No unbounded autonomous tool use
- ❌ No live order execution
- ❌ No broker mutation
- ❌ No external-product dependency in public narrative
- ❌ No burying common functions
- ❌ No long debate transcript as the main UI
- ❌ No backtest performance without hygiene gates
- ❌ No pretending private instruments have direct public RSI
- ❌ No mismatch between investor language and live product behavior

---

## 4. Seven-Day Operating Model

This plan assumes intense parallel execution.

### Roles:

#### Product/UI Lead
Owns:
- Packet UX
- Common actions
- Graph surfaces
- Pitchdeck format
- Demo flow

#### Backend/Data Lead
Owns:
- PostgreSQL persistence
- Schemas
- Adapters
- Metric snapshots
- API endpoints
- Audit logs

#### Agent/Model Lead
Owns:
- Provider abstraction
- Ollama/hosted model path
- Coordinator
- Specialist roles
- Structured outputs
- Tool boundaries

#### Quant/Backtest Lead
Owns:
- Indicators
- Volatility
- Backtest_plan
- Eligibility gates
- Controlled runner
- Graph verification
- Evals

#### Risk/Evaluation Lead
Owns:
- Risk monitors
- Outcome attribution
- Tests
- Eval fixtures
- Workflow metrics
- Demo validation

#### Product Narrative Lead
Owns:
- index33-aligned messaging consistency across docs, deck, and demo scripts
- claim-to-feature truth checking so investor language matches implemented capability

**If only one or two people are implementing, these roles become time blocks rather than people. The scope remains the same; the schedule becomes brutal.**

---

## 5. Day 1: Product Surface And Schema Lock

### Goal

Lock the product shape and make the north star visible in the app.

### Build

- [ ] Update product language across README, UI, docs, and pitch outline
- [ ] Add index33-compatible product framing in docs/deck copy while preserving quant-workflow north star
- [ ] Map existing build surfaces to investor-facing product labels:
  - Decisions = decision-packet workflow
  - Swarm Private = specialist collaboration layer
  - Enterprise Marketplace = governance/tool boundary surface and roadmap
- [ ] Implement decision-packet UI layout
- [ ] Add common-action bar
- [ ] Add packet sections:
  - Signal
  - Market snapshot
  - Technicals
  - Sentiment
  - Inter-market
  - Fundamentals
  - Bull/bear
  - Validation/backtest
  - Risk
  - Confidence
  - Decision
  - Audit
- [ ] Add TypeScript packet types
- [ ] Add backend packet/review schema extensions
- [ ] Add deterministic sample packets
- [ ] Add provider metadata fields
- [ ] Add graph containers and deterministic demo graph data
- [ ] Add pitchdeck outline

### Exit Gate

The app visually presents Ambrosia as a quant workflow agent with a complete packet
shape and common actions.

---

## 6. Day 2: Durable Memory And Audit

### Goal

Replace demo-only state with durable system-of-record foundations.

### Build

- [ ] Activate PostgreSQL migrations for:
  - review_packet
  - decision_audit
  - metric_snapshot
  - retrieval_event
  - outcome_record
- [ ] Add API endpoints:
  - POST /packets (create)
  - GET /packets/{id} (retrieve)
  - GET /packets (list with filter/search)
  - POST /packets/{id}/audit (record audit event)
  - GET /packets/{id}/audit (retrieve audit history)
- [ ] Add packet retrieval endpoints with source/confidence fields
- [ ] Add sample packet fixtures to seeding script
- [ ] Add API response audit logging
- [ ] Verify local fallback still works when DB is unavailable
- [ ] Document schema version and migration path

### Exit Gate

New packets persist in PostgreSQL. Audit trail is recorded and retrievable. The app
gracefully falls back to deterministic demo when DB is unavailable.

---

## 7. Day 3: Market Data, Technicals, And Graphs

### Goal

Wire market data adapters and render verifiable quant graphs.

### Build

- [ ] Implement market-data adapter layer with:
  - One working data source (e.g., Yahoo Finance, Polygon, or IEX)
  - One deterministic fallback (CSV or synthetic data)
  - Clear labeling of data provenance in UI
- [ ] Implement technical-indicator calculator:
  - Moving averages (30, 50, 200-day)
  - RSI (14-period)
  - MACD
  - Volatility (realized, implied if available)
  - Volume analysis
  - Trend state
- [ ] Add TypeScript types for market snapshot and technicals
- [ ] Render graphs on packet UI:
  - Price + moving averages
  - RSI
  - Volume
  - Volatility
  - Trend indicator
- [ ] Add confidence/source indicator on each graph
- [ ] Wire common actions: "Refresh metrics", "View technicals"
- [ ] Document data provenance in audit log

### Exit Gate

Packets render real or deterministic market data with clear provenance. Graphs are
readable by traders and quants. Common actions work.

---

## 8. Day 4: Sentiment, Alerts, And Common Actions

### Goal

Implement sentiment analysis, TradingView alert intake, and polish common actions.

### Build

- [ ] Implement sentiment adapter layer with:
  - One working source (news sentiment, social sentiment, or RSS)
  - Fallback to deterministic demo source
  - Clear labeling of sentiment origin
- [ ] Implement TradingView alert intake:
  - Webhook endpoint with signature verification
  - Prompt-injection protection
  - Alert queue with provenance
  - Convert alert to packet shell
- [ ] Implement common actions:
  - New packet (form)
  - Generate thesis (call agent/LLM or deterministic stub)
  - Ingest alert (from TradingView or manual)
  - Refresh metrics (update market data)
  - Record decision (UI form, persist to DB)
  - Set follow-up (reminder, task queue)
  - Export report (PDF or markdown)
- [ ] Add sentiment section to packet UI
- [ ] Add inter-market context lookup (stocks, bonds, commodities, FX correlation hints)
- [ ] Update pitchdeck outline with sentiment and alerts

### Exit Gate

Sentiment and alerts flow into packets. Common actions are accessible and working.
TradingView integration is hardened.

---

## 9. Day 5: Provider Abstraction And Agent Roles

### Goal

Implement model-provider abstraction and route to specialist agents.

### Build

- [ ] Implement provider abstraction layer supporting:
  - Deterministic fallback (existing)
  - Local Ollama (if available)
  - Hosted provider (OpenAI, Anthropic, etc., if credentials available)
  - Hybrid mode (fallback chain)
  - Config/credentials management
- [ ] Ensure provider/tool capability statements in investor demo reflect actual runtime modes enabled
- [ ] Implement specialist agent roles with structured outputs:
  - Market-data agent (fetch and contextualize)
  - Technical agent (RSI, MACD, trend interpretation)
  - Sentiment agent (news, social, consensus)
  - Inter-market agent (correlation, regime)
  - Fundamental agent (earnings, ratios, quality)
  - Quant agent (backtest readiness, validation gates)
  - Bull agent (thesis support, opportunity framing)
  - Bear agent (thesis critique, disconfirming evidence)
  - Risk agent (drawdown, concentration, tail risk)
  - PM agent (synthesis, decision readiness, follow-up)
- [ ] Implement coordinator workflow that:
  - Routes user packet input to all specialists in parallel
  - Collects structured outputs
  - Passes to PM agent for synthesis
  - Updates packet with all agent outputs
- [ ] Add structured-output TypeScript types for each role
- [ ] Implement MCP-compatible tool boundaries (or explicit internal boundaries if
  full MCP is deferred):
  - Market_data_tools
  - Retrieval_tools
  - Indicator_tools
  - Sentiment_tools
  - Backtest_tools
  - Report_tools
  - Risk_tools
- [ ] Add provider metadata to audit log

### Exit Gate

Packets flow through specialist agents. Outputs are structured and retrievable.
Provider layer supports local and hosted models with transparent fallback.

---

## 10. Day 6: Backtesting, Risk, And Evaluation

### Goal

Implement backtest gates, risk monitoring, and evaluation framework.

### Build

- [ ] Implement backtest_plan schema with:
  - Entry/exit rules
  - Assumptions
  - Lookback period
  - Holding period
  - Risk constraints
  - Hygiene gates (max loss, min signal strength, etc.)
- [ ] Implement eligibility gates:
  - Signal must be recent and strong enough
  - Liquidity must be adequate
  - No correlated open positions
  - Portfolio impact must be acceptable
  - Risk budget must allow trade size
- [ ] Implement controlled backtest runner:
  - One working backtest path for narrow, valid case (e.g., simple mean-reversion on liquid equities)
  - Clearly labeled scope and assumptions
  - Out-of-sample test if data permits
  - Drawdown and Sharpe verification
  - Export backtest report
- [ ] Implement risk-monitoring objects and dashboard:
  - Active position tracking
  - P&L monitoring
  - Correlation/factor overlap checks
  - VaR/drawdown alert thresholds
  - Follow-up trigger state
- [ ] Implement outcome-attribution schema:
  - Trade entry/exit
  - P&L realization
  - Thesis vs. backtest vs. actual
  - Next-packet state (reopened, closed, watch)
- [ ] Implement tests and eval fixtures:
  - Backtest hygiene checks
  - Invalid-backtest refusal scenarios
  - Unsupported-claim detection
  - Workflow-speed metrics
  - Graph verification
- [ ] Wire common actions: "Prepare backtest", "Run eligible backtest", "View risks"

### Exit Gate

Packets can trigger controlled backtests with guarded eligibility. Risk monitoring is
active. Outcomes are tracked and attributed. Evaluation framework validates packet
integrity and workflow speed.

---

## 11. Day 7: Portfolio Context, Pitch Deck, And Demo

### Goal

Close product surface, validation, and investor demo.

### Build

- [ ] Implement portfolio-context schema:
  - Exposure summary (long, short, net, gross)
  - Concentration by sector, factor, instrument
  - Related positions and factor overlap
  - Risk budget and sizing constraints
  - No live broker integration; advisory mode only
- [ ] Implement confidence-derivation fields:
  - Evidence score (thesis, historical, research)
  - Technical score (signal strength, pattern fit)
  - Sentiment score (news, social, regime)
  - Inter-market score (correlation, spillover risk)
  - Validation score (backtest results, validation gates passed)
  - Tradeability score (liquidity, execution risk, slippage)
  - Risk-adjusted score (Sharpe, max drawdown, Kelly fit)
  - Overall confidence with blockers and source/proxy penalties
- [ ] Create pitch deck outline or markdown deck:
  - Product positioning (quant workflow agent)
  - North-star narrative
  - Feature tour with screenshots or placeholders
  - Packet flow walkthrough
  - Backtest hygiene and risk monitoring
  - Differentiation vs. competitors
  - Go-to-market and next steps
- [ ] Prepare coherent investor/private-beta demo:
  - One end-to-end packet workflow with real or deterministic data
  - Common actions demonstrated
  - Backtest example with guardrails
  - Risk monitoring alert triggered
  - Outcome attribution on a closed trade
  - Matches product narrative and pitch deck
- [ ] Final product-language audit:
  - README updated with quant agent positioning
  - UI language aligned across all sections
  - All non-negotiables verified (no fake data, no hidden provenance, etc.)
- [ ] Final investor-narrative audit:
  - index33 external language is consistent with live product behavior
  - three-product framing is represented without overclaiming unbuilt capability
- [ ] Documentation completeness:
  - IMPLEMENTATION_NOTES updated with Day 1–7 status
  - Provider abstraction and fallback strategy documented
  - Data sources and fallback paths clearly labeled in UI
  - Backtest scope and hygiene gates documented
  - Evaluation results and pending work documented
  - Next-phase roadmap (e.g., live broker, more data sources, advanced ML)

### Exit Gate

Ambrosia is a presentable, end-to-end quant workflow agent. The product shape is locked,
all non-negotiables are honored, and the investor demo flows coherently. The codebase
is documented for next-phase handoff.

---

## 8. Checklist For Success

- [ ] Product identity is clearly "quant workflow agent" across UI and docs
- [ ] Decision packet is rendered with all 13 required sections
- [ ] Common actions are accessible from every view
- [ ] Market data is real or clearly deterministic with source labeling
- [ ] Technical indicators (RSI, MA, volatility, volume, trend) are calculated and rendered
- [ ] Sentiment is integrated with labeled source
- [ ] TradingView alerts flow into packets with hygiene checks
- [ ] PostgreSQL persistence is active with audit logs
- [ ] Retrieval is hybrid (reviews + notes + sources) with audit
- [ ] Provider abstraction supports local (Ollama) and hosted models with fallback
- [ ] Specialist agents produce structured outputs routed by coordinator
- [ ] Backtest eligibility gates prevent invalid trades
- [ ] Risk monitoring is active with follow-up triggers
- [ ] Portfolio context is advisory (no live execution)
- [ ] Confidence score reflects evidence, technical, sentiment, validation, risk, and tradeability
- [ ] Evaluation fixtures validate packet hygiene and workflow speed
- [ ] Pitch deck is presentable with product narrative
- [ ] Demo flows end-to-end and matches deck narrative
- [ ] Investor-facing product labels (Decisions, Swarm Private, Enterprise Marketplace) map clearly to actual implemented surfaces
- [ ] All non-negotiables are honored (no fake data, no hidden provenance, etc.)
- [ ] Documentation is complete and next-phase roadmap is clear

---

## 9. Next Phases (Post Day 7)

After Day 7, prioritize:

1. **Live Broker Integration**: Sandbox broker connectivity for order entry and live P&L.
2. **Advanced Market Data**: Multi-source aggregation, alternative data (crypto, commodities).
3. **Model Fine-Tuning**: Specialist agents trained on historical decisions and outcomes.
4. **Backtesting Engine**: Full-featured backtester with walk-forward analysis and parameter optimization.
5. **Factor Attribution**: Deep attribution of P&L to thesis components, technical triggers, sentiment signals.
6. **Collaborative Features**: Multi-user packet review, permission tiers, internal compliance audit.
7. **Mobile/Alerts**: Mobile app and push alerts for risk triggers and follow-ups.
8. **Advanced Sentiment**: Earnings call sentiment, insider trading signal, dark pool flow.

---

## 10. References

- [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) — Current MVP status and first upgrade path
- [INVESTOR_PRESENTATION.md](INVESTOR_PRESENTATION.md) — Product pitch and positioning
- [README.md](../README.md) — Build and run instructions
- [../../papers/index33.txt](../../papers/index33.txt) — Investor business summary input for narrative alignment
