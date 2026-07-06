# Ambrosia

Ambrosia is an agentic investment decision platform. It turns a signal, alert, watchlist move, market question, or trade thesis into a structured, auditable, risk-aware review before capital is put at risk.

The product is organized around three connected surfaces:

- Decisions: agentic review workflows for pre-trade investment decisions.
- Swarm Private: private specialist-agent collaboration for portfolio, risk, market, and thesis analysis.
- Enterprise Agentic Swarm Marketplace: governed workflows, admin controls, visibility checks, and deployable enterprise modules.

## Current State

Ambrosia is now a working monorepo with a Next.js frontend, a FastAPI backend, a Rust hot-path service boundary, local full-stack scripts, CI validation, and production deployment wiring.

The Index84 implementation and closure chain is fully wired and passing in repository scope:

- Roadmap completion evidence gate passes.
- Literal feature coverage gate passes.
- Hot-path design/readiness gate passes.
- Phase 7 hot-path governance go/no-go gate passes.
- Index86 closure gate passes.

Recent implementation developments (July 2026):

- Index95 implementation baseline is live in repository scope, including durable signal lifecycle storage, idempotent write behavior, and expanded control-plane contracts.
- A dedicated Signals page is now available at `/signals` and linked in the left navigation.
- Market Scanner now supports natural alpha formation with a primary `Promote to Alpha` action and lifecycle-aware candidate controls.
- New backend convenience route `POST /scanner/candidates/promote-alpha` creates hypothesis + signal + link in one call.
- Scanner promotion lifecycle visibility is available at `GET /scanner/candidates/promotions`.
- Review intake now supports an optional `Create Alpha from Review` path for intentional thesis-origin alpha creation.

The frontend includes:

- Dashboard and review workbench
- New Review flow with review creation and re-access paths
- Review detail pages at `/review/[id]`
- Discovery / market intelligence surface
- Market Scanner lifecycle actions including `Promote to Alpha`, `Create Review`, and validation queueing
- Alpha Lab origin visibility for scanner-promoted objects (origin, source ticker/signal, promotion metadata)
- Signals inventory surface at `/signals`
- History, calibration, team, reports, governance, admin, and advanced operations pages
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
- Expanded signal writeback and lifecycle endpoints for validation, policy transitions, and outcome rollups

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
- Playwright, pytest, Ruff, visibility checks, eval scripts, and stack contract tests
- Render deployment entrypoints through root `index.js` and `render.yaml`

## Repository Layout

The root is intentionally kept small. Configuration and entrypoint files stay at the top level; operational notes, archives, helper scripts, and logs live in focused subfolders.

- `apps/web/` - Next.js frontend
- `services/api/` - FastAPI backend
- `services/hotpath-rs/` - Rust deterministic hot-path service (kill switch + pre-trade risk checks)
- `packages/evals/` - evaluation and ablation runners
- `packages/schemas/` - shared schema contracts
- `scripts/` - deployment, validation, local stack, and automation scripts
- `scripts/dev/` - lower-level development helper scripts moved out of the root
- `docs/` - implementation notes, deployment notes, roadmap documents, and verification records
- `docs/session-archives/` - historical index artifacts, including `index69.txt`
- `infra/` - database schema and migration scaffolding
- `tests/` - stack and integration tests
- `artifacts/` - ignored local logs and generated artifacts

## Local Development

Requirements:

- Node.js 20+
- pnpm 9.x
- Python 3.12
- uv

Install dependencies:

```powershell
pnpm install
```

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

## Roadmap

1. Restore and continuously verify production API health on Render.
2. Move advanced sandbox state from in-memory fallback behavior into durable PostgreSQL-backed storage.
3. Expand review lifecycle persistence across accounts, teams, and historical search.
4. Connect more frontend operating panels directly to live advanced backend endpoints.
5. Expand provider ablations, evaluation reporting, and regression gates.
6. Harden enterprise governance, marketplace packaging, and permission boundaries.
7. Add broker-sandbox workflows, advanced attribution, mobile alerting, and portfolio-level action loops.

## Patch Notes

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
