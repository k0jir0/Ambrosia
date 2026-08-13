-- Index160: durable, tenant-scoped, outbound-only Ollama review bridge.
ALTER TABLE local_worker_credentials
  ALTER COLUMN user_id DROP NOT NULL,
  ADD COLUMN IF NOT EXISTS created_by_subject TEXT,
  ADD COLUMN IF NOT EXISTS capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS capability_digest CHAR(64),
  ADD COLUMN IF NOT EXISTS worker_version TEXT,
  ADD COLUMN IF NOT EXISTS ollama_version TEXT,
  ADD COLUMN IF NOT EXISTS last_ip_prefix TEXT,
  ADD COLUMN IF NOT EXISTS max_concurrent_jobs INTEGER NOT NULL DEFAULT 1
    CHECK (max_concurrent_jobs BETWEEN 1 AND 16);

ALTER TABLE llm_jobs DROP CONSTRAINT IF EXISTS llm_jobs_state_check;
ALTER TABLE llm_jobs ADD CONSTRAINT llm_jobs_state_check CHECK (state IN
  ('queued','claimed','completed','failed','canceled','cancelled','retry_wait','superseded','expired'));
ALTER TABLE llm_jobs
  ADD COLUMN IF NOT EXISTS operation_id UUID,
  ADD COLUMN IF NOT EXISTS requested_model TEXT,
  ADD COLUMN IF NOT EXISTS requested_model_digest TEXT,
  ADD COLUMN IF NOT EXISTS required_context_length INTEGER NOT NULL DEFAULT 8192
    CHECK (required_context_length BETWEEN 1024 AND 1000000),
  ADD COLUMN IF NOT EXISTS lease_id UUID,
  ADD COLUMN IF NOT EXISTS lease_generation INTEGER NOT NULL DEFAULT 0 CHECK (lease_generation >= 0),
  ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
  ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS workflow_stage TEXT NOT NULL DEFAULT 'queued',
  ADD COLUMN IF NOT EXISTS last_error JSONB;

CREATE TABLE IF NOT EXISTS ollama_review_operations (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  expected_packet_version INTEGER NOT NULL CHECK (expected_packet_version >= 1),
  job_id UUID REFERENCES llm_jobs(id) ON DELETE SET NULL,
  idempotency_key_hash CHAR(64),
  semantic_key_hash CHAR(64) NOT NULL,
  provider_requested TEXT NOT NULL DEFAULT 'ollama' CHECK (provider_requested='ollama'),
  provider_used TEXT,
  state TEXT NOT NULL CHECK (state IN
    ('queued','leased','running','verifying','repairing','retry_wait','completed','failed','expired','canceled','superseded')),
  stage TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  reason_code TEXT,
  input_hash CHAR(64) NOT NULL,
  result_hash CHAR(64),
  requested_model TEXT,
  requested_model_digest TEXT,
  model_name TEXT,
  model_digest TEXT,
  worker_id UUID REFERENCES local_worker_credentials(id) ON DELETE SET NULL,
  deadline_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  fallback_operation_id UUID REFERENCES ollama_review_operations(id) ON DELETE SET NULL,
  result_packet_version INTEGER,
  trace_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  error JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, idempotency_key_hash)
);

ALTER TABLE llm_jobs DROP CONSTRAINT IF EXISTS llm_jobs_operation_id_fkey;
ALTER TABLE llm_jobs ADD CONSTRAINT llm_jobs_operation_id_fkey
  FOREIGN KEY (operation_id) REFERENCES ollama_review_operations(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS llm_job_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  job_id UUID NOT NULL REFERENCES llm_jobs(id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
  worker_id UUID REFERENCES local_worker_credentials(id) ON DELETE SET NULL,
  lease_id UUID NOT NULL,
  lease_generation INTEGER NOT NULL CHECK (lease_generation >= 1),
  lease_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  lease_expires_at TIMESTAMPTZ NOT NULL,
  last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  stage TEXT NOT NULL DEFAULT 'claimed',
  stage_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  model_name TEXT,
  model_digest TEXT,
  worker_version TEXT,
  ollama_version TEXT,
  failure_code TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  UNIQUE (job_id, lease_generation)
);

CREATE TABLE IF NOT EXISTS llm_operation_events (
  id BIGSERIAL PRIMARY KEY,
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  operation_id UUID NOT NULL REFERENCES ollama_review_operations(id) ON DELETE CASCADE,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  from_state TEXT,
  to_state TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  attempt_id UUID REFERENCES llm_job_attempts(id) ON DELETE SET NULL,
  trace_id TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_runs_one_result_per_job ON llm_runs(job_id) WHERE job_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ollama_active_semantic_key
  ON ollama_review_operations(organization_id,semantic_key_hash)
  WHERE state NOT IN ('failed','expired','canceled','superseded');
CREATE INDEX IF NOT EXISTS idx_ollama_operations_packet ON ollama_review_operations(organization_id,packet_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ollama_operations_state ON ollama_review_operations(organization_id,state,deadline_at);
CREATE INDEX IF NOT EXISTS idx_llm_jobs_model_claim ON llm_jobs(organization_id,state,requested_model_digest,next_attempt_at,created_at) WHERE state IN ('queued','retry_wait');
CREATE INDEX IF NOT EXISTS idx_llm_jobs_lease_expiry ON llm_jobs(organization_id,lease_expires_at) WHERE state='claimed';
CREATE INDEX IF NOT EXISTS idx_llm_job_attempts_job ON llm_job_attempts(organization_id,job_id,attempt_number DESC);
CREATE INDEX IF NOT EXISTS idx_llm_operation_events_operation ON llm_operation_events(organization_id,operation_id,created_at);

ALTER TABLE ollama_review_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_job_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_operation_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ollama_review_operations;
DROP POLICY IF EXISTS tenant_isolation ON llm_job_attempts;
DROP POLICY IF EXISTS tenant_isolation ON llm_operation_events;
CREATE POLICY tenant_isolation ON ollama_review_operations USING(organization_id=ambrosia_current_organization_id()) WITH CHECK(organization_id=ambrosia_current_organization_id());
CREATE POLICY tenant_isolation ON llm_job_attempts USING(organization_id=ambrosia_current_organization_id()) WITH CHECK(organization_id=ambrosia_current_organization_id());
CREATE POLICY tenant_isolation ON llm_operation_events USING(organization_id=ambrosia_current_organization_id()) WITH CHECK(organization_id=ambrosia_current_organization_id());
GRANT SELECT,INSERT,UPDATE,DELETE ON ollama_review_operations,llm_job_attempts,llm_operation_events TO ambrosia_runtime;
GRANT USAGE,SELECT ON SEQUENCE llm_operation_events_id_seq TO ambrosia_runtime;
