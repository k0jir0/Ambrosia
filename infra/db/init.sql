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

CREATE TABLE IF NOT EXISTS review_embeddings (
  review_id UUID PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
  embedding vector(1536),
  search_text tsvector
);

CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_pointers_review ON source_pointers(review_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_review ON audit_events(review_id);
CREATE INDEX IF NOT EXISTS idx_review_embeddings_search ON review_embeddings USING GIN(search_text);