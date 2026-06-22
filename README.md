# Ambrosia Trade Review

Ambrosia Trade Review is a pre-trade adversarial review MVP. A user brings a market thesis before acting; Ambrosia structures it, challenges it, produces validation/refusal logic, surfaces tradeability questions, captures a decision state, and stores the review as decision memory.

https://ambrosia-5aec.onrender.com/

## Current State

The MVP is implemented as a working monorepo with a polished Next.js workbench and a FastAPI backend. The frontend is usable as an investor-demo workbench with sample reviews, automatic thesis seeding, API-backed review creation when the backend is available, and deterministic local fallback when it is not.

Deployment state:

- Fresh Render web service is live from this repository on `main`.
- Public URL: `https://ambrosia-5aec.onrender.com/`
- Render service ID: `srv-d8s9ga6gvqtc73fuccb0`
- The earlier Render project/service was deleted and recreated cleanly as a Node web service.

Implemented frontend capabilities:

- Direct workbench-first experience, not a landing page or chat UI.
- Manual thesis intake.
- `Generate thesis` button that seeds candidate review inputs without presenting them as recommendations.
- API-first review creation through the FastAPI `/reviews` endpoint.
- Local deterministic fallback if the API is unavailable.
- Structured Trade Review artifact with critique, disconfirming test, historical analogue, validation/refusal panel, claims, tradeability checklist, evidence pointers, decision strip, and audit trace.
- Decision state buttons: pursue, watch, reject, and needs more data.
- Functional left navigation for Review workbench, Decision memory, Calibration, and Source library.
- Live dashboard metrics derived from current review state.
- Visible form validation errors.
- Playwright smoke tests for desktop and tablet viewports.

Implemented backend capabilities:

- FastAPI health endpoint.
- In-memory review store for MVP/demo use.
- Deterministic review generator matching the MVP artifact shape.
- Review list, create, detail, decision update, outcome update, and TradingView webhook routes.
- Prompt-injection screening for TradingView webhook payloads.
- Pydantic schemas for the review artifact and decision updates.
- pytest and Ruff verification.

Implemented architecture scaffolding:

- PostgreSQL and pgvector-ready schema in `infra/db/init.sql`.
- Workflow notes for the future LangGraph implementation.
- MCP-style tool adapter notes.
- Shared schema documentation.
- Evaluation fixtures and a runnable eval fixture gate.

## MVP Scope

The first build focuses on one loop:

1. Submit a thesis.
2. Normalize claims and assumptions.
3. Generate a structured Trade Review artifact.
4. Surface adversarial critique and a disconfirming test.
5. Produce a validation specification or refusal reason.
6. Ask tradeability questions.
7. Capture pursue, watch, reject, or needs more data.
8. Record confidence, trial count, outcome placeholder, and audit events.

## Repository Layout

```text
apps/web                 Next.js investor-presentable workbench
services/api             FastAPI MVP API and deterministic review generator
services/workflows       LangGraph workflow placeholder and architecture notes
services/tools           MCP-style tool adapter contracts
packages/schemas         Shared schema documentation
packages/evals           Evaluation fixtures and test corpus
infra/db                 PostgreSQL schema and migration seed
docs                     Product and implementation notes
```

## Tech Stack

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod
- Lucide icons
- Playwright
- Recharts
- Radix/shadcn-style dependency baseline

Backend:

- Python
- FastAPI
- Pydantic
- SQLAlchemy-ready schema design
- PostgreSQL and pgvector target schema
- Structured audit events
- uv
- pytest
- Ruff

Infrastructure and scaffolding:

- Docker Compose for PostgreSQL/pgvector and Redis targets
- PostgreSQL schema seed
- Evaluation fixtures for refusal, prompt injection, and tradeability checks
- LangGraph workflow placeholder
- MCP-style tool adapter contracts

## Local Development

Required runtimes:

- Node.js 20 or newer
- pnpm 9.x
- Python 3.12
- uv

Install dependencies from the repo root:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia
pnpm install
cd services\api
uv sync
```

Run the API:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia\services\api
uv run uvicorn app.main:app --reload --port 8000
```

Run the web app:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia
pnpm dev:web
```

Local URLs:

- Web app: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

The frontend is resilient for demos: it attempts to use the API first and falls back to local deterministic generation if the API is unavailable.

## Render Deployment

For the current Render web service, use the Ambrosia repository on `main`.

Live service:

- URL: `https://ambrosia-5aec.onrender.com/`
- Service ID: `srv-d8s9ga6gvqtc73fuccb0`
- Runtime: `node`
- Branch: `main`
- Root Directory: `.`
- Build Command: `pnpm build`
- Start Command: `node index.js`

If the service root directory is the repository root:

```bash
Build Command: pnpm build
Start Command: node index.js
```

If the service root directory is `apps/web`:

```bash
Build Command: pnpm build
Start Command: node index.js
```

Both start paths bind to Render's `$PORT`. Leave `NEXT_PUBLIC_API_BASE_URL` unset unless a live Ambrosia API service URL is available.

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

Current verification status:

- Frontend build passes.
- Frontend lint passes.
- Playwright e2e passes, including generated-thesis, navigation-panel, decision-button, source-library, and dark-mode flows.
- Backend tests pass.
- Backend lint passes.
- Eval fixture gate passes against the deterministic backend generator.
- Stack contract tests pass.
- VS Code diagnostics show no errors.

## GitHub

Private repository:

```text
https://github.com/k0jir0/Ambrosia
```

Default branch:

```text
main
```

## Next Implementation Steps

1. Replace in-memory API storage with PostgreSQL persistence.
2. Add pgvector hybrid retrieval over reviews, notes, and source pointers.
3. Add LangGraph workflow nodes behind the existing API contract.
4. Add model provider integration and heterogeneous adversarial critique.
5. Promote `packages/evals` into CI.
6. Add a small protected internal inspection surface for workflow runs, retrieval sets, tool calls, refusal reasons, and eval results.

## Design Principle

This MVP intentionally avoids a terminal clone, chat-first interface, live execution, naive backtest results, large same-model agent committees, and premature distributed systems.

The product proof is decision discipline, not architecture spectacle.
