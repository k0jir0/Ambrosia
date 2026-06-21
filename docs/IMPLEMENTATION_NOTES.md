# Implementation Notes

## What Is Implemented First

- A Next.js workbench with realistic sample reviews and local review generation.
- A FastAPI service with deterministic review generation and in-memory persistence.
- PostgreSQL target schema for the future durable system of record.
- Evaluation fixtures for refusal, prompt injection, and tradeability checks.

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