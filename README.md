# Ambrosia

## Project Overview

Ambrosia is an agentic investment decision platform. It turns a signal, alert, watchlist move, market question, or trade thesis into a structured, auditable, risk-aware review before capital is put at risk.

The product is organized around three connected surfaces:

- Decisions: agentic review workflows for pre-trade investment decisions.
- Swarm Private: private specialist-agent collaboration for portfolio, risk, market, and thesis analysis.
- Enterprise Agentic Swarm Marketplace: governed workflows, admin controls, visibility checks, and deployable enterprise modules.

## Features

Implemented features include:

- Adversarial review workflow for investment theses, alerts, scanner candidates, and watchlist ideas.
- Human-controlled decision capture with auditable review, packet, outcome, and signal memory.
- Market Scanner, Alpha Lab, and signal lifecycle workflows for moving from candidate thesis to measurable alpha.
- Signal Decision Proposal with finance-native actions, signal writeback, execution readiness, and evidence requirements.
- Signals cockpit with formulas, universes, horizons, benchmarks, validation state, risk posture, review links, and next actions.
- Next.js frontend surfaces for dashboard, review workbench, intake, discovery, scanner, alpha, signals, history, calibration, team, reports, governance, admin, relay benchmarks, platform, enterprise, execution intelligence, and CLI design.
- FastAPI backend routes for reviews, packets, market data, scanner runs, sentiment, retrieval, risk, reports, coordinator runs, signals, backtests, paper trades, execution intelligence, enterprise governance, and readiness evidence.
- Deterministic local fallback behavior when hosted services or market providers are unavailable.
- Provider abstraction for deterministic local execution, Ollama, hosted models, and hybrid specialist-agent workflows.
- PostgreSQL-ready persistence scaffolding for packet, audit, memory, signal lifecycle, and feedback data.
- Rust hot-path service boundary for deterministic pre-trade checks, order validity, notional limits, and kill-switch behavior.
- Python SDK and Typer CLI for local and hosted operator workflows.
- Unit, stack, API, E2E, visibility, evaluation, migration, scorecard, and deployment-readiness checks.

## Current State

Ambrosia is a working monorepo with a Next.js frontend, a FastAPI backend, a Rust hot-path service boundary, a Python CLI/SDK layer, local full-stack scripts, CI validation, and Render deployment wiring.

The current product loop is no longer just review generation. The repository now supports a finance-native decision path:

1. Scanner, Alpha Lab, Signals, or review intake creates a candidate thesis.
2. The candidate can become a measurable alpha hypothesis and signal.
3. Adversarial Review evaluates the thesis, records evidence, and captures a human decision.
4. Signal Decision Proposal translates the review into a finance action.
5. The signal records `BUY`, `SELL`, `HOLD`, `HEDGE`, `RISK_ADJUST`, `BLOCK`, or `RETIRE` plus execution readiness.
6. Signals, outcomes, scorecards, execution intelligence, and history carry the decision forward.

The Index84 closure chain remains wired in repository scope:

- Roadmap completion evidence gate.
- Literal feature coverage gate.
- Hot-path design/readiness gate.
- Phase 7 hot-path governance go/no-go gate.
- Index86 closure gate.

Current July 2026 implementation developments:

- Index97 seeded signal lifecycle inventory exists for demo and validation flows.
- A dedicated Signals cockpit at `/signals` shows formulas, universes, horizons, benchmarks, validation state, risk posture, stack links, review links, latest signal action, execution readiness, and next action.
- Review workbench now includes Signal Decision Proposal, an explicit final handoff that writes adversarial review decisions back into signal memory.
- Signal Decision Proposal can create a linked alpha hypothesis and signal when a review has no valid signal link, then write the selected finance action.
- Backend signal decision writeback accepts finance-native actions, records execution readiness, enforces evidence/verifier/date requirements for promotion-style decisions, and persists lifecycle snapshots.
- Market Scanner supports natural alpha formation with `Promote to Alpha`, candidate lifecycle controls, and promotion records.
- `POST /scanner/candidates/promote-alpha` creates hypothesis + signal + link in one call.
- `GET /scanner/candidates/promotions` exposes scanner promotion lifecycle visibility.
- Review intake supports an optional `Create Alpha from Review` path for intentional thesis-origin alpha creation.
- CLI and SDK packages cover hosted/local status, review, packet, market, relay, signal, backtest, paper-trade, and enterprise operations.

The frontend includes:

- Dashboard and review workbench
- New Review flow with review creation and re-access paths
- Review detail pages at `/review/[id]`
- Discovery / market intelligence surface
- Market Scanner lifecycle actions including `Promote to Alpha`, `Create Review`, and validation queueing
- Alpha Lab origin visibility for scanner-promoted objects (origin, source ticker/signal, promotion metadata)
- Signals cockpit at `/signals`
- Signal Decision Proposal in the review workbench, including editable finance actions and signal writeback confirmation
- History, calibration, team, reports, governance, admin, and advanced operations pages
- Relay Benchmarks, Platform, Enterprise, Execution Intelligence, and CLI Design pages
- Global navigation with the Operating Model panel visible beneath the Admin pressable banner
- API-first behavior with deterministic local fallback when services are unavailable
- Visible paragraphs describing Agentic AI for Investments, Investment Trading Decisions, Swarm Intelligence, and Agentic Swarm

The backend includes:

- Review creation, retrieval, and packet workflow routes
- Market data, scanner, sentiment, retrieval, risk, report, and coordinator modules
- Provider abstraction for deterministic, Ollama, hosted, and hybrid specialist runs
- Stateful sandbox routes for advanced operating functions such as orders, positions, attribution, alerts, admin audit, and guardrail policy updates
- PostgreSQL-ready schema and migration scaffolding for durable packet, audit, and memory storage
- Index84 platform routes for relay, feature store MVP, signals, backtests, paper trades, execution intelligence, enterprise governance, and readiness/evidence flows
- Extended alpha and execution intelligence surfaces including alpha hypothesis, alpha decay analytics, warm-path event processing, and enterprise security packet endpoints
- Scanner-to-alpha promotion routes with durable lifecycle snapshots and promotion record persistence
- Expanded signal writeback and lifecycle endpoints for validation, policy transitions, review links, decision writeback, outcome writeback, and outcome rollups
- Index97 signal/review seed routes for lifecycle demonstrations and regression checks
- CLI/SDK-facing contracts for hosted and local operations

The hot-path service includes:

- Separate Rust service boundary at `services/hotpath-rs/`
- Deterministic pre-trade checks for order validity and notional limits
- Kill-switch command path for immediate local reject behavior
- Explicit no-LLM-in-live-order-loop boundary

## Product Thesis

Ambrosia is Agentic AI for Investments because it decomposes an investment question into coordinated specialist tasks, generates review packets, records evidence, exposes uncertainty, and keeps the human decision maker in control.

Ambrosia supports Investment Trading Decisions by converting thesis intake into a repeatable path: market context, specialist critique, risk evaluation, confidence synthesis, decision memory, and follow-up reporting.

Ambrosia is Swarm Intelligence because specialist outputs are routed through a coordinator instead of being shown as isolated summaries. The system compares perspectives, preserves disagreement, and produces a more disciplined final packet.

Ambrosia is an Agentic Swarm because the workflow is not a static dashboard. Agents can be assigned roles, called through provider modes, evaluated through gates, and surfaced through UI modules that map to operating decisions.

## Architecture

- Monorepo root with pnpm workspaces
- Next.js 15.1.0 frontend with React 19
- FastAPI backend with Python 3.12
- Rust hot-path execution service scaffold for deterministic low-latency order gating
- SQLAlchemy and PostgreSQL-oriented schema patterns
- Provider modes for deterministic local execution, Ollama, hosted models, and hybrid operation
- Python SDK and Typer-based CLI for operator workflows and automation
- Playwright, pytest, Ruff, visibility checks, eval scripts, and stack contract tests
- Render deployment entrypoints through root `index.js` and `render.yaml`

## Technologies Used

- Frontend: Next.js 15.1.0, React 19, TypeScript, Playwright, and pnpm workspaces.
- Backend: Python 3.12, FastAPI, Pydantic, pytest, Ruff, and uv.
- Persistence and infrastructure: PostgreSQL-oriented schema patterns, SQLAlchemy-ready migrations, and Render deployment wiring.
- Execution hot path: Rust service scaffold for deterministic pre-trade gating and kill-switch behavior.
- CLI and SDK: Python SDK package and Typer-based Ambrosia CLI.
- AI/provider layer: deterministic local engine, Ollama mode, hosted model mode, and hybrid provider resolution.
- Quality and validation: unit tests, stack contract tests, API tests, Playwright E2E tests, visibility checks, eval scripts, retrieval benchmarks, provider ablation checks, scorecard checks, and migration checks.

## Repository Layout

The root is intentionally kept small. Configuration and entrypoint files stay at the top level; operational notes, archives, helper scripts, and logs live in focused subfolders.

- `apps/web/` - Next.js frontend
- `services/api/` - FastAPI backend
- `services/hotpath-rs/` - Rust deterministic hot-path service (kill switch + pre-trade risk checks)
- `packages/cli/` - Ambrosia CLI package and command contracts
- `packages/sdk-python/` - Python SDK package
- `packages/evals/` - evaluation and ablation runners
- `packages/schemas/` - shared schema contracts
- `scripts/` - deployment, validation, local stack, and automation scripts
- `scripts/dev/` - lower-level development helper scripts moved out of the root
- `docs/` - implementation notes, deployment notes, roadmap documents, and verification records
- `docs/session-archives/` - historical index artifacts, including `index69.txt`
- `infra/` - database schema and migration scaffolding
- `tests/` - stack and integration tests
- `artifacts/` - ignored local logs and generated artifacts

## Installation Instructions

Requirements:

- Node.js 20+
- pnpm 9.x
- Python 3.12
- uv

Install dependencies:

```powershell
pnpm install
```

## Usage

Run the full local stack:

```powershell
pnpm local:serve
```

Useful local commands:

- `pnpm local:start` launches the stack in detached mode
- `pnpm local:stop` stops the local stack
- `pnpm local:status` checks whether web and API are responding
- `pnpm local:logs` tails local stack logs from `.local/`
- `pnpm local:web:serve` runs only the web app
- `pnpm local:api:serve` runs only the API

Primary user flow:

1. Open the web app and start from review intake, scanner, alpha lab, or signals.
2. Create or promote a candidate thesis.
3. Run adversarial review to inspect evidence, critique, validation hygiene, and tradeability.
4. Capture a human decision such as pursue, watch, reject, or needs more data.
5. Use Signal Decision Proposal to write the decision back to signal memory when a linked signal exists or is created.
6. Monitor outcomes, scorecards, signal lifecycle state, execution readiness, and follow-up actions.

## Verification

Common checks from the repository root:

```powershell
pnpm build:web
pnpm lint:web
pnpm test:e2e
pnpm test:api
pnpm lint:api
pnpm visibility:check
pnpm evals
pnpm evals:ablation
pnpm evals:retrieval
pnpm evals:scanner
pnpm db:migrations:check
pnpm scorecard:check
pnpm m1:readiness
pnpm test:stack
pnpm signals:index97:check
pnpm docs:consistency:check
```

Index84 and closure checks:

```powershell
pnpm roadmap:completion:check
pnpm index84:literal:check
pnpm hotpath:design:check
python scripts/verify-index86-closure.py
```

Synthetic monitoring:

```powershell
python scripts/synthetic-monitor.py --base-url https://ambrosia-api-69t6.onrender.com
```

Recent verification status:

- Web build and lint were brought back to green locally.
- API test suite was brought to green locally.
- Scanner promotion endpoint and promotion listing tests are passing locally.
- Signal decision writeback API coverage verifies `decisionAction` and `executionReadiness` updates.
- Playwright workbench coverage verifies Signal Decision Proposal visibility, stale-link recovery, and sanitized signal creation.
- Signals cockpit coverage verifies stack links, risk posture, and next-action visibility.
- Visibility and provider workflow gates are green in GitHub Actions.
- The production web surface is live at `https://ambrosia-5aec.onrender.com/`.
- The split production web/API stack is live at `https://ambrosia-web-c3ax.onrender.com/` and `https://ambrosia-api-69t6.onrender.com/health`.
- The existing production web URL is also configured with `NEXT_PUBLIC_API_URL=https://ambrosia-api-69t6.onrender.com`.

## Render

Current Render settings:

- Repo: `https://github.com/k0jir0/Ambrosia`
- Branch: `main`
- Root Directory: `.`
- Build Command: `pnpm build`
- Start Command: `node index.js`

Live product:

- Existing web: `https://ambrosia-5aec.onrender.com/`
- Split-stack web: `https://ambrosia-web-c3ax.onrender.com/`
- API health target: `https://ambrosia-api-69t6.onrender.com/health`
- Staging web: `https://ambrosia-web-staging.onrender.com/`
- Staging API service is configured with required database mode enabled.

GitHub production deploy wiring exists, but Render deploy hook secrets must be populated for automated hook-triggered deployment. When the hook variables are empty, the GitHub deploy workflow can pass while skipping the Render trigger steps.

## Selective Integration Governance

Ambrosia now includes the hardened selective-integration lifecycle described in `docs/SELECTIVE_INTEGRATION_IMPLEMENTATION.md`. It adds typed packet provenance, non-skippable disconfirmation and deterministic risk stages, guarded human packet decisions, version invalidation, durable outcome memory, and a chain-head-anchored audit ledger. Run `python scripts/verify-selective-integration.py` for the deterministic readiness gate.

Production rollout is controlled by `SELECTIVE_INTEGRATION_ENABLED` and `SELECTIVE_INTEGRATION_ENFORCED`. Apply database migration `v0007` and complete staging certification before enabling enforcement.

## Future Improvements

Areas for potential enhancement and additional features:

1. Continuously verify production and staging API health on Render, including cold-start behavior.
2. Move remaining advanced sandbox and lifecycle fallback state into durable PostgreSQL-backed storage.
3. Expand review and signal lifecycle persistence across accounts, teams, historical search, and outcome cohorts.
4. Tighten the Signal Decision Proposal path with richer risk-budget, liquidity, cost, approval, and outcome requirements.
5. Connect more frontend operating panels directly to live advanced backend endpoints.
6. Expand provider ablations, evaluation reporting, regression gates, and benchmark provenance.
7. Harden enterprise governance, marketplace packaging, service-account lifecycle, SSO, and permission boundaries.
8. Add broker-sandbox workflows, advanced attribution, mobile alerting, and portfolio-level action loops.

## Patch Notes

### Signal Decision Loop Upgrade (Current Baseline)

This release closes the previously missing handoff between adversarial review and signal state.

What shipped:

- Signal Decision Proposal panel in the review workbench
- Editable finance action vocabulary: `BUY`, `SELL`, `HOLD`, `HEDGE`, `RISK_ADJUST`, `BLOCK`, `RETIRE`
- Automatic alpha hypothesis and signal creation for review-derived decisions when no valid signal link exists
- Stale signal-link retry path that creates a replacement signal before writeback
- Signal decision writeback to `/signals/{signal_id}/writeback-decision`
- Execution readiness writeback (`not_executable`, `paper_trade_ready`, `execution_candidate`, `execution_blocked`)
- Evidence, verifier, review-date, decision-quality, and outcome-writeback fields in the backend contract
- Signals cockpit rendering for latest action, execution readiness, linked reviews, validation state, and next action
- Playwright coverage for proposal visibility, stale-link recovery, and sanitized generated signal fields
- API coverage for decision action and execution readiness persistence

Current constraints:

- Signal memory can persist through PostgreSQL when `DATABASE_URL` is configured; otherwise it uses the local lifecycle snapshot artifact.
- Advanced execution remains sandboxed and gated; Signal Decision Proposal records state and does not execute trades.
- Production deploy automation still depends on Render hook secrets being populated in GitHub.

### Index84 Upgrade (Current Baseline)

This release consolidates the Index84 roadmap into executable code and evidence gates.

What shipped:

- Route/OpenAPI contract hardening and exposure-filtered artifacts
- SDK/CLI expansion with enterprise and execution operations
- Feature store MVP, signal workflows, and structured backtest path
- Relay and benchmark chain with FinanceBench, FinQA, and TAT-QA fixtures
- Open FinLLM routing map artifact generation and validation
- Decision-memory attribution and alpha-decay evidence fixtures
- Enterprise lifecycle controls (service account create/rotate/revoke), SSO configuration, audit export, offline bundle manifest, and support/security packet
- Release provenance and packaging evidence (checksums, release evidence, rollout packet)
- Frontend control-plane matrix and frontend quality evidence generation
- Rust hot-path service boundary scaffold with deterministic order gating and kill switch

Key verification artifacts:

- `artifacts/index84-completion.json`
- `artifacts/index84-literal-completion.json`
- `artifacts/hotpath-readiness.json`
- `artifacts/hotpath-phase7-governance.json`
- `artifacts/rollout-evidence-packet.json`
- `artifacts/enterprise-execution-readiness.json`

## Repository

Private repository: `https://github.com/k0jir0/Ambrosia`

Application: `https://ambrosia-5aec.onrender.com/`

Production API: `https://ambrosia-api-69t6.onrender.com/`
