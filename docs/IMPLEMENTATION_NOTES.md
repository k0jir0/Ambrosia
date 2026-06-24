# Implementation Notes

## Current Status: Day 1 (Product Surface & Schema Lock) - COMPLETED ✅

**Date**: 2026-06-24

### Day 2 Progress (Durable Memory & Audit) - IN PROGRESS 🟡

- ✅ Added packet API endpoints:
	- `POST /packets`
	- `GET /packets/{id}`
	- `GET /packets` (with `search`, `ticker`, `decision_state` filters)
	- `POST /packets/{id}/audit`
	- `GET /packets/{id}/audit`
- ✅ Added in-memory packet persistence and audit event recording in API store
- ✅ Added optional PostgreSQL-backed packet persistence adapter (`DATABASE_URL`), with automatic fallback to in-memory mode when DB is unavailable
- ✅ Added Day 2 durable-memory tables in DB init:
	- `review_packet`
	- `decision_audit`
	- `metric_snapshot`
	- `retrieval_event`
	- `outcome_record`
- ✅ Added automated API test coverage for packet create/get/list/audit flows
- ⏳ Full migration/versioning workflow and DB-backed retrieval metrics are still pending (next Day 2 target)

### Day 3 Progress (Market Data, Technicals, Graph Inputs) - IN PROGRESS 🟡

- ✅ Added market data adapter layer with live-or-fallback behavior:
	- Live path: Yahoo Finance chart API (when reachable)
	- Deterministic fallback path: seeded synthetic series when live data is unavailable
- ✅ Added technical indicator calculator:
	- RSI (14)
	- MACD line/signal/histogram
	- MA(30), MA(50), MA(200)
	- Realized volatility and trend classification
- ✅ Added new API endpoints:
	- `GET /market/{ticker}/snapshot`
	- `GET /market/{ticker}/technicals`
	- `POST /packets/{id}/metrics/refresh`
- ✅ Added packet metric refresh persistence hooks:
	- API updates packet `marketSnapshot` and `technicals`
	- Metric snapshots are recorded to `metric_snapshot` when PostgreSQL is enabled
- ✅ Wired web common action "Refresh Metrics" to call market/technical APIs and log provenance-aware audit entries
- ✅ Added automated tests for market snapshot, technical endpoints, and packet metric refresh flow

### Day 1 Deliverables (Completed)

- ✅ **Product Identity**: Ambrosia repositioned as a "quant workflow agent"
- ✅ **Decision-Packet UI**: All 13 required sections scaffolded and displayable
- ✅ **Common Actions Bar**: 13 standard trader/PM actions with tooltips
- ✅ **TypeScript Types**: Extended packet schema with all quant workflow agent fields
- ✅ **Python Models**: Pydantic models for backend packet storage and API contracts
- ✅ **Sample Data**: One fully populated sample decision packet demonstrating end-to-end workflow
- ✅ **Pitch Deck**: 22-slide outline explaining product positioning and go-to-market
- ✅ **7-Day Roadmap**: Complete execution plan for Days 2-7 with exit gates and role assignments

### Packet Schema: Review → Packet

**Old (review.v1)**:
- Claims (sourced, assumption, inference, contradiction)
- Critique and disconfirming test
- Validation specification and tradeability questions
- Decision state (pursue, watch, reject, needs_more_data)
- Audit trail and sources

**New (packet.v1)** — extends review with:
- **Market Snapshot**: Price, volume, market cap, data provenance (live/fallback/demo)
- **Technical Indicators**: RSI, MACD, moving averages, volatility, trend, data quality
- **Sentiment**: Overall score, news/social breakdown, trend direction, source confidence
- **Inter-Market**: Correlations (benchmark, commodities, bonds, FX), regime, spillover risk
- **Fundamentals**: P/E, P/B, ROE, debt-to-equity, growth rate, quality score
- **Backtest Plan & Results**: Status, entry/exit rules, assumptions, lookback period, Sharpe/max drawdown, validity score, hygiene issues
- **Risk Monitor**: Position size, concentration, correlationoverlap, VaR, alert thresholds, status
- **Portfolio Context**: Gross/net/long/short exposure, sector and factor concentration, related positions, risk budget, sizing constraints
- **Confidence Breakdown**: Evidence, technical, sentiment, inter-market, validation, tradeability, risk-adjusted scores + blockers
- **Specialist Agent Outputs**: 10 parallel agents (market data, technical, sentiment, inter-market, fundamental, quant, bull, bear, risk, PM synthesis) with summaries, scores, and provider metadata
- **Coordinator Metadata**: Version, provider info, fallback chain

### Files Created/Modified (Day 1)

**Components**:
- `apps/web/src/components/common-actions.tsx` — NEW: 13-action bar with icons and tooltips
- `apps/web/src/components/decision-packet.tsx` — NEW: Full packet UI with all 13 sections, metrics, confidence bars, helper components

**Types & Models**:
- `apps/web/src/lib/types.ts` — Extended with DecisionPacket and all quant fields
- `services/api/app/models.py` — Extended with Pydantic models for packet schema

**Sample Data**:
- `apps/web/src/lib/sample-data.ts` — Added samplePackets array with realistic tech-rotation example (market data, technicals, sentiment, inter-market, backtest, risk, all agent outputs)

**Documentation**:
- `docs/SEVEN_DAY_ROADMAP.md` — NEW: Complete 7-day execution plan (Days 1-7 with builds, exit gates, roles, checklists)
- `docs/PITCH_DECK.md` — NEW: 22-slide pitch deck outline (problem, solution, features, architecture, use cases, go-to-market, ask)
- `README.md` — Updated product language from "pre-trade adversarial review" to "quant workflow agent"

## What Is Implemented First

- A Next.js workbench with realistic sample reviews and local review generation.
- A FastAPI service with deterministic review generation and in-memory persistence.
- PostgreSQL target schema for the future durable system of record.
- Evaluation fixtures for refusal, prompt injection, and tradeability checks.
- **NEW**: Decision packet UI with common actions and full quant workflow visualization.
- **NEW**: Specialist agent output framework (10 roles) with structured outputs.

## Why The Backend Generator Is Deterministic

The first implementation must work without model credentials. The deterministic generator encodes the review artifact shape, refusal behavior, audit events, and decision states. It can later be replaced by the LangGraph workflow while preserving the same schemas.

## Current Integration State

The web app now attempts to create reviews through the FastAPI `/reviews` endpoint and falls back to the deterministic local generator if the API is unavailable. This keeps the investor demo resilient while preserving the API-backed path.

## First Upgrade Path

1. Replace in-memory API storage with PostgreSQL persistence.
2. Add pgvector hybrid retrieval over reviews and notes.
3. Add LangGraph workflow nodes behind the same API contract.
4. Add model providers and heterogeneous adversarial critique.
5. Promote `packages/evals` into CI.

## 7-Day Hardcore Completion Roadmap

A detailed 7-day plan to transform Ambrosia from an MVP review tool into a full quant workflow agent is available in [SEVEN_DAY_ROADMAP.md](SEVEN_DAY_ROADMAP.md).

This roadmap compresses the 90-day vision into a 7-day intensive execution schedule with:
- Decision-packet UI with all required sections (signal, market snapshot, technicals, sentiment, inter-market, fundamentals, bull/bear, validation, risk, confidence, decision, audit)
- Durable PostgreSQL persistence with audit trails
- Market data and technical indicator adapters
- Sentiment integration and TradingView alert intake
- Model-provider abstraction supporting local Ollama and hosted models
- Specialist agent roles (technical, fundamental, sentiment, risk, bull, bear, PM synthesis)
- Controlled backtesting with eligibility gates
- Risk monitoring and portfolio context
- Confidence scoring with multiple factor inputs
- Comprehensive evaluation framework
- Investor-ready pitch deck and demo

**Key non-negotiables**: no fake data, no hidden provenance, no model-only confidence, no unbounded tool use, no live order execution, no broker mutations, and no burying common functions.