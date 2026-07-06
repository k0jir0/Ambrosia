CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  schema_version TEXT NOT NULL DEFAULT 'review.v1',
  workflow_version TEXT NOT NULL DEFAULT 'adversarial-review.v1',
  title TEXT NOT NULL,
  thesis TEXT NOT NULL,
  ticker TEXT,
  asset_class TEXT,
  time_horizon TEXT,
  intended_expression TEXT,
  decision_state TEXT CHECK (decision_state IN ('pursue', 'watch', 'reject', 'needs_more_data')),
  confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
  trial_count_impact INTEGER NOT NULL DEFAULT 1,
  follow_up_date DATE,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_pointers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID REFERENCES reviews(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  permission TEXT NOT NULL,
  source_timestamp TEXT,
  relevance REAL,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID REFERENCES reviews(id) ON DELETE CASCADE,
  workflow_run_id TEXT,
  event_type TEXT NOT NULL,
  detail TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID REFERENCES reviews(id) ON DELETE CASCADE,
  idempotency_key TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL,
  workflow_version TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  error TEXT
);

CREATE TABLE IF NOT EXISTS review_packet (
  packet_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL DEFAULT 'packet.v1',
  workflow_version TEXT NOT NULL DEFAULT 'quant-agent.v1',
  ticker TEXT,
  decision_state TEXT CHECK (decision_state IN ('pursue', 'watch', 'reject', 'needs_more_data')),
  confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  artifact JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  detail TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metric_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  metric_type TEXT NOT NULL,
  metric_payload JSONB NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  confidence REAL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outcome_record (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  outcome TEXT NOT NULL,
  outcome_date DATE,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roadmap_plan (
  plan_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  workstream TEXT NOT NULL,
  owner TEXT NOT NULL DEFAULT 'TBD',
  quality TEXT NOT NULL CHECK (quality IN ('P0', 'P1', 'P2', 'P3', 'P4')),
  status TEXT NOT NULL CHECK (status IN ('proposed', 'scoped', 'active', 'blocked', 'done', 'deferred')),
  target_milestone TEXT,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roadmap_decision (
  decision_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES roadmap_plan(plan_id) ON DELETE CASCADE,
  decision_type TEXT NOT NULL,
  quality TEXT NOT NULL CHECK (quality IN ('D0', 'D1', 'D2', 'D3', 'D4', 'D5')),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roadmap_outcome (
  outcome_id TEXT PRIMARY KEY,
  decision_id TEXT NOT NULL REFERENCES roadmap_decision(decision_id) ON DELETE CASCADE,
  quality TEXT NOT NULL CHECK (quality IN ('O0', 'O1', 'O2', 'O3', 'O4', 'O5')),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS release_evidence_packet (
  id TEXT PRIMARY KEY,
  roadmap_plan_ids TEXT[] NOT NULL DEFAULT '{}',
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS review_embeddings (
  review_id UUID PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
  embedding vector(1536),
  search_text tsvector
);

CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_pointers_review ON source_pointers(review_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_review ON audit_events(review_id);
CREATE INDEX IF NOT EXISTS idx_review_embeddings_search ON review_embeddings USING GIN(search_text);
CREATE INDEX IF NOT EXISTS idx_review_packet_ticker ON review_packet(ticker);
CREATE INDEX IF NOT EXISTS idx_review_packet_created_at ON review_packet(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_audit_packet ON decision_audit(packet_id);
CREATE INDEX IF NOT EXISTS idx_metric_snapshot_packet ON metric_snapshot(packet_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_event_packet ON retrieval_event(packet_id);
CREATE INDEX IF NOT EXISTS idx_outcome_record_packet ON outcome_record(packet_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_plan_status ON roadmap_plan(status);
CREATE INDEX IF NOT EXISTS idx_roadmap_plan_workstream ON roadmap_plan(workstream);
CREATE INDEX IF NOT EXISTS idx_roadmap_decision_plan ON roadmap_decision(plan_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_outcome_decision ON roadmap_outcome(decision_id);
CREATE INDEX IF NOT EXISTS idx_paper_trade_decision ON paper_trade(decision_id);
CREATE INDEX IF NOT EXISTS idx_execution_fill_trade ON execution_fill(paper_trade_id);
CREATE INDEX IF NOT EXISTS idx_service_account_status ON service_account(status);
CREATE INDEX IF NOT EXISTS idx_audit_export_status ON audit_export_job(status);
CREATE INDEX IF NOT EXISTS idx_relay_run_benchmark ON relay_run(benchmark);
CREATE INDEX IF NOT EXISTS idx_point_in_time_feature_ticker_as_of ON point_in_time_feature(ticker, as_of);
CREATE INDEX IF NOT EXISTS idx_signal_definition_status ON signal_definition(status);
CREATE INDEX IF NOT EXISTS idx_backtest_run_signal ON backtest_run(signal_id);
CREATE INDEX IF NOT EXISTS idx_market_replay_ticker ON market_replay_run(ticker);
CREATE INDEX IF NOT EXISTS idx_platform_release_evidence_status ON platform_release_evidence_packet(status);
CREATE INDEX IF NOT EXISTS idx_feedback_record_store_ticker ON feedback_record_store(LOWER(ticker));
CREATE INDEX IF NOT EXISTS idx_feedback_record_store_created_at ON feedback_record_store(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_idempotency_record_endpoint ON api_idempotency_record(endpoint);