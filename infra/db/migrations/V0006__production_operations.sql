-- Index119 production operations: durable jobs, security audit chain, and replay control.

CREATE TABLE IF NOT EXISTS durable_job (
  id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  idempotency_key TEXT,
  state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  input_summary TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
  max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
  timeout_seconds INTEGER NOT NULL DEFAULT 300 CHECK (timeout_seconds BETWEEN 1 AND 3600),
  lease_owner TEXT,
  lease_expires_at TIMESTAMPTZ,
  cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
  result JSONB,
  error TEXT,
  queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  UNIQUE (job_type, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_durable_job_claim
  ON durable_job (state, queued_at) WHERE state = 'queued';
CREATE INDEX IF NOT EXISTS idx_durable_job_lease
  ON durable_job (lease_expires_at) WHERE state = 'running';

CREATE TABLE IF NOT EXISTS security_audit_event (
  sequence_id BIGINT PRIMARY KEY,
  event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
  request_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  previous_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_security_audit_actor_time
  ON security_audit_event (actor_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_security_audit_request
  ON security_audit_event (request_id);

CREATE TABLE IF NOT EXISTS execution_replay_guard (
  nonce TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  approval_digest CHAR(64) NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_replay_expiry ON execution_replay_guard (expires_at);
