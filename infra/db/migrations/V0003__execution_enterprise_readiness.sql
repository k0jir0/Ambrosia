-- Ambrosia DB migration
-- Version: v0003
-- Purpose: paper decision loop, execution intelligence, and enterprise governance evidence

CREATE TABLE IF NOT EXISTS paper_trade (
  paper_trade_id TEXT PRIMARY KEY,
  decision_id TEXT REFERENCES roadmap_decision(decision_id) ON DELETE SET NULL,
  ticker TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy', 'sell', 'long', 'short')),
  quantity NUMERIC NOT NULL CHECK (quantity > 0),
  status TEXT NOT NULL DEFAULT 'open',
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_fill (
  fill_id TEXT PRIMARY KEY,
  paper_trade_id TEXT REFERENCES paper_trade(paper_trade_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  decision_price NUMERIC NOT NULL,
  fill_price NUMERIC NOT NULL,
  implementation_shortfall_bps NUMERIC NOT NULL,
  latency_ms INTEGER NOT NULL,
  latency_fitness TEXT NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_account (
  service_account_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scopes TEXT[] NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled', 'rotating')),
  token_fingerprint TEXT NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_export_job (
  export_job_id TEXT PRIMARY KEY,
  requested_by TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  scope TEXT NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_paper_trade_decision ON paper_trade(decision_id);
CREATE INDEX IF NOT EXISTS idx_execution_fill_trade ON execution_fill(paper_trade_id);
CREATE INDEX IF NOT EXISTS idx_service_account_status ON service_account(status);
CREATE INDEX IF NOT EXISTS idx_audit_export_status ON audit_export_job(status);