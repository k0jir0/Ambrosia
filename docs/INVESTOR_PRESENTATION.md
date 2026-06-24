# Ambrosia Investor Presentation

As of June 23, 2026

## Opening

Ambrosia is a pre-trade adversarial review product.

Its purpose is simple: before an investor commits capital, Ambrosia forces the thesis through structured skepticism. It turns a raw idea into claims, assumptions, disconfirming tests, tradeability questions, validation requirements, and a recorded decision.

Most investment tools help people find more ideas. Ambrosia helps investors decide which ideas should not be traded yet. That is the wedge.

## Current State

Ambrosia is now a working MVP.

The product has a Next.js workbench, a FastAPI backend, a deterministic review engine, schema-backed review artifacts, and a live deployment path on Render. The current app is designed around one core workflow: enter a thesis, generate an adversarial review, inspect the critique, and record the human decision.

The workbench supports manual thesis intake, generated thesis examples, API-backed review creation, and a local deterministic fallback when the backend is unavailable. This makes the demo resilient while preserving the API path for production.

A review includes the thesis, ticker or instrument, asset class, time horizon, intended expression, confidence, trial-count impact, strongest critique, disconfirming test, historical analogue, validation specification, tradeability checklist, source pointers, and an audit trail.

The decision state is intentionally explicit. A user can mark a review as pursue, watch, reject, or needs more data. This turns Ambrosia from a one-time analysis tool into decision memory.

## What Has Been Built

Ambrosia now has a usable investor-facing product surface.

The workbench includes four operating views: review workbench, decision memory, calibration dashboard, and source library. It opens directly into the product experience, not a marketing page.

The backend exposes review creation, review listing, review retrieval, decision recording, outcome recording, a TradingView webhook, health checks, and basic metrics. This gives the product a real API contract rather than a front-end-only prototype.

The review engine already handles important guardrails. It refuses naive performance or backtest scoring when point-in-time data, transaction costs, liquidity, and trial budget are not specified. It also detects instruction-like text in market-alert payloads and treats it as untrusted data.

The data foundation is in place. Ambrosia has a `review.v1` schema, Pydantic models, and a PostgreSQL/pgvector-ready database scaffold covering reviews, source pointers, audit events, workflow runs, and embeddings.

The deployment foundation is also in place. Render configuration exists for both the web app and API service, with Node and Python runtimes pinned.

## Accomplishments

The first accomplishment is product clarity. Ambrosia is not another idea-generation chatbot. It is a discipline layer for investment decisions.

The second accomplishment is a working MVP. The app can be opened, a thesis can be generated or entered, a structured adversarial review can be produced, and a decision can be recorded.

The third accomplishment is a durable artifact design. The review object is structured enough to support auditability, retrieval, validation, and future model orchestration.

The fourth accomplishment is safety and quality control. Ambrosia already encodes refusal behavior, prompt-injection resistance, tradeability checks, and validation hygiene.

The fifth accomplishment is test coverage. Playwright covers the web workbench flows. Pytest covers API behavior. Stack contract tests check that the repository still matches the MVP architecture. Eval fixtures cover refusal behavior, prompt injection, tradeability gaps, and disconfirming-test quality.

The sixth accomplishment is demo readiness. The frontend can run against the API, but it can also fall back locally, which means an investor demo does not fail just because a backend service is unavailable.

## Why It Matters

Ambrosia creates value by making investment judgment more repeatable.

In most workflows, the record of why a trade was considered, rejected, deferred, or pursued is scattered across notes, chats, spreadsheets, and memory. Ambrosia centralizes that decision process.

Over time, this becomes proprietary decision memory. The system can remember what was reviewed, what evidence mattered, what questions blocked action, what decisions were made, and what happened afterward.

That memory is the long-term asset. It can improve research discipline, reduce repeated mistakes, support post-decision calibration, and make institutional investment processes more auditable.

## Near-Term Roadmap

The next step is to replace in-memory API storage with PostgreSQL persistence.

After that, Ambrosia should add pgvector retrieval over prior reviews, notes, and source pointers. This will allow each new review to draw on the investor's own decision history.

The workflow layer can then move from deterministic generation to model-backed adversarial critique, with LangGraph-style orchestration behind the existing API contract.

The eval suite should be promoted into CI before private beta, so every model or workflow change is tested against core product behaviors.

The private beta target should focus on a narrow group of investors who already have repeatable thesis-review workflows and feel the cost of poor decision memory.

## Closing

Ambrosia has moved from concept to working product foundation.

It has a clear problem, a focused wedge, a demoable MVP, a real API, a structured schema, a deployment path, safety guardrails, and tests.

The opportunity now is to turn this foundation into a private beta product where every review makes the system more valuable. Ambrosia is building the infrastructure for investment restraint, repeatability, and memory before capital is put at risk.
