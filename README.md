# Ambrosia

Ambrosia is a pre-trade adversarial review product. It helps an investor pressure-test a thesis before acting by structuring the argument, challenging assumptions, surfacing disconfirming evidence, and recording the decision.

## What It Does

Ambrosia turns a raw thesis into a structured review:

- normalizes claims and assumptions
- generates a critique and disconfirming test
- asks tradeability and validation questions
- returns a decision state such as pursue, watch, reject, or needs more data
- stores the review as decision memory

## Why It Matters

Most investment workflows are optimized for idea generation, not idea rejection. Ambrosia is designed to make the decision process more disciplined, repeatable, and auditable before capital is committed.

## Current Status

The MVP is live as a working monorepo with a Next.js workbench and a FastAPI backend. The frontend supports API-backed review creation and deterministic local fallback when the backend is unavailable.

Live deployment:

- URL: `https://ambrosia-5aec.onrender.com/`
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

Local URLs:

- Web app: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## Render

Current Render settings:

- Repo: `https://github.com/k0jir0/Ambrosia`
- Branch: `main`
- Root Directory: `.`
- Build Command: `pnpm build`
- Start Command: `node index.js`

Both start paths bind to Render's `$PORT`. Leave `NEXT_PUBLIC_API_BASE_URL` unset unless a live Ambrosia API URL is available.

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

1. Replace in-memory API storage with PostgreSQL persistence.
2. Add pgvector retrieval over reviews, notes, and source pointers.
3. Add workflow orchestration behind the existing API contract.
4. Add model-provider integration for richer adversarial critique.
5. Promote evals into CI.

## Repository

Private repository: `https://github.com/k0jir0/Ambrosia`
Application: `https://ambrosia-5aec.onrender.com/`
