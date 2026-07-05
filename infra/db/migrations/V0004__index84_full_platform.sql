-- Ambrosia DB migration
-- Version: v0004
-- Purpose: full Index84 platform surfaces for relay, features, signals, backtests, release evidence, and enterprise audit

CREATE TABLE IF NOT EXISTS relay_run (
  relay_run_id TEXT PRIMARY KEY,
  benchmark TEXT NOT NULL,
  question TEXT NOT NULL,
  route TEXT NOT NULL,
  trace JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS point_in_time_feature (
  feature_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  ticker TEXT NOT NULL,
  as_of TIMESTAMPTZ NOT NULL,
  value NUMERIC NOT NULL,
  source TEXT NOT NULL,
  point_in_time BOOLEAN NOT NULL DEFAULT true,
  provenance JSONB NOT NULL DEFAULT '[]'::jsonb,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_definition (
  signal_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  universe TEXT[] NOT NULL DEFAULT '{}',
  horizon TEXT NOT NULL,
  formula TEXT NOT NULL,
  cost_model TEXT NOT NULL,
  benchmark TEXT NOT NULL,
  validation_gates TEXT[] NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN ('hypothesis', 'alpha_candidate', 'retired')),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backtest_run (
  backtest_id TEXT PRIMARY KEY,
  signal_id TEXT REFERENCES signal_definition(signal_id) ON DELETE SET NULL,
  status TEXT NOT NULL,
  sample_period TEXT NOT NULL,
  metrics JSONB NOT NULL,
  hygiene_issues TEXT[] NOT NULL DEFAULT '{}',
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_replay_run (
  replay_id TEXT PRIMARY KEY,
  ticker TEXT NOT NULL,
  scenario TEXT NOT NULL,
  latency_ms INTEGER NOT NULL,
  result TEXT NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform_release_evidence_packet (
  release_evidence_id TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  status TEXT NOT NULL,
  checksums JSONB NOT NULL DEFAULT '{}'::jsonb,
  package_surfaces JSONB NOT NULL DEFAULT '[]'::jsonb,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relay_run_benchmark ON relay_run(benchmark);
CREATE INDEX IF NOT EXISTS idx_point_in_time_feature_ticker_as_of ON point_in_time_feature(ticker, as_of);
CREATE INDEX IF NOT EXISTS idx_signal_definition_status ON signal_definition(status);
CREATE INDEX IF NOT EXISTS idx_backtest_run_signal ON backtest_run(signal_id);
CREATE INDEX IF NOT EXISTS idx_market_replay_ticker ON market_replay_run(ticker);
CREATE INDEX IF NOT EXISTS idx_platform_release_evidence_status ON platform_release_evidence_packet(status);
