-- Ambrosia DB migration
-- Version: v0005
-- Purpose: index95 durability completion and API idempotency storage

CREATE TABLE IF NOT EXISTS signal_lifecycle_snapshot (
  snapshot_key TEXT PRIMARY KEY,
  artifact JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback_record_store (
  feedback_id TEXT PRIMARY KEY,
  packet_id TEXT,
  ticker TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  time_horizon TEXT NOT NULL,
  decision_state TEXT NOT NULL,
  confidence INTEGER NOT NULL,
  outcome TEXT NOT NULL,
  outcome_date TEXT NOT NULL,
  pnl NUMERIC,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_idempotency_record (
  idempotency_key TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL,
  response_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_record_store_ticker ON feedback_record_store(LOWER(ticker));
CREATE INDEX IF NOT EXISTS idx_feedback_record_store_created_at ON feedback_record_store(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_idempotency_record_endpoint ON api_idempotency_record(endpoint);
