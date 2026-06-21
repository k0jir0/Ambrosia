# Ambrosia Trade Review

Ambrosia Trade Review is a pre-trade adversarial review MVP. A user brings a market thesis before acting; Ambrosia structures it, challenges it, produces validation/refusal logic, surfaces tradeability questions, captures a decision state, and stores the review as decision memory.

This repository implements the first product loop described in `../papers/index18.txt`, `../papers/index19.txt`, `../papers/index20.txt`, and `../papers/index21.txt`.

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

Backend:

- Python
- FastAPI
- Pydantic
- SQLAlchemy-ready schema design
- PostgreSQL and pgvector target schema
- Structured audit events

## Local Development

This workspace was generated in an environment where Node.js and Python were not available, so dependencies were not installed here.

Once Node.js and Python are installed:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia
pnpm install
pnpm dev:web
```

In another terminal:

```powershell
cd C:\Users\user\Desktop\ARC\Ambrosia\services\api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

The frontend is designed to run with realistic local sample data even before the backend is connected.

## Design Principle

This MVP intentionally avoids a terminal clone, chat-first interface, live execution, naive backtest results, large same-model agent committees, and premature distributed systems.

The product proof is decision discipline, not architecture spectacle.