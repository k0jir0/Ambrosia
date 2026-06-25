# Ambrosia

Ambrosia is an agent-native trading and investment decision platform for financial decisioning in an AI-driven world. It turns a signal, alert, watchlist move, market question, or trade thesis into an organized, data-aware, risk-aware decision workflow before money is put at risk.

Ambrosia is organized around three product surfaces:

- Decisions: the Agentic Quant Workflow AI for structured pre-trade decision packets
- Swarm Private: specialist multi-agent collaboration with explicit coordinator routing
- Enterprise Agentic Swarm Marketplace: governed, serverized workflows with tool-boundary scaffolding

## What It Does

Ambrosia packages the repeated work of trading and investment decisioning into one auditable workflow:
- generates a review from a thesis or alert
- enriches the case with market data, technicals, sentiment, and related context
- runs specialist agents for market data, technicals, sentiment, fundamentals, inter-market, quant validation, bull case, bear case, risk, and PM synthesis
- produces critique, disconfirming tests, validation plans, and tradeability questions
- prepares controlled backtests and evaluates risk with explicit refusal gates
- derives multi-factor confidence and updates packet state
- records the complete audit trail, outcome, and follow-up memory

## Current State

The current monorepo includes a working Next.js workbench and a FastAPI backend. The implemented workflow supports API-backed review and packet actions with deterministic fallback behavior when external services are unavailable.

What is currently live in the product:

- workbench-first review and packet workflow
- manual thesis intake and generated thesis seeds
- Generate thesis support for quick starts
- API-first review creation and retrieval
- market metrics refresh for snapshot, technicals, and sentiment
- Run Agent Swarm with coordinator-driven specialist outputs
- prepare backtest, evaluate risk, derive confidence, and record decision flows
- decision memory, source navigation, and report-oriented packet views
- Functional left navigation between workbench, memory, calibration, and sources
- Live dashboard metrics in the workbench and summary views
- Visible form validation errors for empty or incomplete thesis inputs
- Local deterministic fallback when external services are unavailable
- provenance-aware fallback disclosure rather than hidden invented data

The current 8-function philosophy is encoded as one connected workflow, not as isolated features.

## Why It Matters

Most investment tools optimize for idea generation. Ambrosia is designed to optimize for idea validation, skepticism, and decision discipline. It keeps human authority explicit while making the workflow repeatable, auditable, and easier to trust.

## Architecture

- Next.js 15.1.0 frontend with React 19
- FastAPI backend with packet, review, market, retrieval, risk, and coordinator routes
- Deterministic local review generation fallback
- Provider abstraction for deterministic, Ollama, hosted, and hybrid specialist runs
- PostgreSQL-ready durable-memory schema and packet/audit storage patterns
- Playwright, pytest, Ruff, and contract-style stack tests

## Local Development

Requirements:

- Node.js 20+
- pnpm 9.x
- Python 3.12
- uv

Common commands from the repository root:

```powershell
pnpm install
```

```powershell
pnpm local:serve
```

Useful local commands:

- `pnpm local:serve` runs the full stack in one terminal
- `pnpm local:start` launches the stack in detached mode
- `pnpm local:stop` stops the local stack
- `pnpm local:status` checks whether web and API are responding
- `pnpm local:logs` tails stack logs from `.local/`
- `pnpm local:web:serve` runs only the web app
- `pnpm local:api:serve` runs only the API

## Render

Current Render settings:

- Repo: `https://github.com/k0jir0/Ambrosia`
- Branch: `main`
- Root Directory: `.`
- Build Command: `pnpm build`
- Start Command: `node index.js`

The live product is served at [https://ambrosia-5aec.onrender.com/](https://ambrosia-5aec.onrender.com/).

## Verification

From the repo root:

```powershell
pnpm build:web
pnpm lint:web
pnpm test:e2e
pnpm test:api
pnpm lint:api
pnpm evals
pnpm evals:ablation
python scripts/synthetic-monitor.py --base-url https://ambrosia-api.onrender.com
pnpm test:stack
```

Synthetic monitoring also runs every 6 hours in GitHub Actions via `.github/workflows/synthetic-monitoring.yml` and uploads `synthetic-monitor-report` artifacts.

## Roadmap

1. Formalize migration/versioning automation and pgvector ranking strategies.
2. Expand provider ablations, eval reporting, and synthetic monitoring in CI.
3. Add scanner-style NYSE thesis discovery and report generation on top of the existing workflow.
4. Add multi-user governance and permission layers for enterprise rollout.
5. Advance post-Day-7 roadmap: broker sandbox, advanced factor attribution, and mobile alerts.

## Repository

Private repository: `https://github.com/k0jir0/Ambrosia`
Application: `https://ambrosia-5aec.onrender.com/`
