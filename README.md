# Ambrosia

Ambrosia is a quant workflow agent for investment decisioning. It structures and pressure-tests investment theses by integrating market data, technical analysis, sentiment, backtesting, and risk monitoring, all while keeping human decision authority explicit and auditable.

Ambrosia is presented across three integrated product surfaces:

- Decisions: agentic AI for investment trading decisions through structured decision packets
- Swarm Private: specialist multi-agent collaboration with explicit coordinator routing
- Enterprise Agentic Swarm Marketplace: governance and MCP-compatible tool-boundary scaffolding for serverized deployment

## What It Does

Ambrosia turns a raw thesis into a decision packet:

- integrates market data, technicals, sentiment, and inter-market analysis
- runs specialist agents (technical, fundamental, sentiment, risk, bear, bull) in parallel
- generates structured critique and validation analysis
- initiates controlled backtesting with eligibility gates
- monitors portfolio context, concentration, and risk
- derives multi-factor confidence scoring
- records the complete decision audit trail
- enables follow-up and outcome attribution

## Why It Matters

Most investment workflows are optimized for idea generation, not idea validation. Ambrosia structures the pre-trade decision process across multiple dimensions—technical, fundamental, sentiment, inter-market, and risk—then gates execution with backtesting and portfolio constraints. Every decision is audited and tied to outcomes, making investment discipline repeatable and data-driven.

## Current Status

The seven-day core roadmap is implemented in a working monorepo with a Next.js workbench and a FastAPI backend. The frontend supports API-backed packet actions with deterministic local fallback when the backend is unavailable.

Live deployment:

- [https://ambrosia-5aec.onrender.com/](https://ambrosia-5aec.onrender.com/)
- Service ID: `srv-d8s9ga6gvqtc73fuccb0`
- Runtime: `node`
- Branch: `main`

## Product Surface

- Workbench-first interface for reviewing a thesis
- Manual thesis intake
- `Generate thesis` support for quick starts
- Structured review artifact with critique, validation, and decision fields
- Decision memory and source navigation
- Dark-mode default presentation

## Architecture

- Next.js frontend
- FastAPI backend
- Deterministic local review generation fallback
- PostgreSQL and pgvector-ready schema scaffold
- Playwright, pytest, and Ruff coverage

## Local Development

Requirements:

- Node.js 20+
- pnpm 9.x
- Python 3.12
- uv

Run locally:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia
pnpm install
cd services\api
uv sync
```

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia\services\api
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia
pnpm dev:web
```

## Render

Current Render settings:

- Repo: `https://github.com/k0jir0/Ambrosia`
- Branch: `main`
- Root Directory: `.`
- Build Command: `pnpm build`
- Start Command: `node index.js`

The live product is served at [https://ambrosia-5aec.onrender.com/](https://ambrosia-5aec.onrender.com/). Leave `NEXT_PUBLIC_API_BASE_URL` unset unless a live Ambrosia API URL is available.

## Verification

From the repo root:

```powershell
pnpm build:web
pnpm lint:web
pnpm test:e2e
pnpm test:api
pnpm lint:api
pnpm evals
pnpm test:stack
```

## Roadmap

1. Formalize migration/versioning automation and pgvector ranking strategies.
2. Add richer graph verification and investor-demo screenshot capture automation.
3. Expand provider ablations and eval reporting in CI.
4. Add multi-user governance and permission layers for enterprise rollout.
5. Advance post-Day-7 roadmap: broker sandbox, advanced factor attribution, and mobile alerts.

## Repository

Private repository: `https://github.com/k0jir0/Ambrosia`
Application: `https://ambrosia-5aec.onrender.com/`
