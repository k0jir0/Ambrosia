-- Index132 productization: first-party identity, tenant isolation, and LLM provenance.
-- Legacy records are deliberately quarantined; they are never assigned to the
-- first customer that signs up.

BEGIN;

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'suspended', 'legacy_quarantine', 'deleted')),
  plan TEXT NOT NULL DEFAULT 'design_partner',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_slug_lower
  ON organizations (lower(slug));

INSERT INTO organizations (id, name, slug, status, plan)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'Legacy data quarantine',
  'legacy-quarantine',
  'legacy_quarantine',
  'internal'
)
ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE FUNCTION ambrosia_current_organization_id()
RETURNS UUID
LANGUAGE SQL
STABLE
AS $$
  SELECT NULLIF(current_setting('app.current_organization_id', true), '')::UUID
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ambrosia_runtime') THEN
    CREATE ROLE ambrosia_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  email_canonical TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  professional_role TEXT NOT NULL DEFAULT 'other'
    CHECK (professional_role IN ('analyst', 'portfolio_manager', 'risk', 'cio_founder', 'other')),
  password_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending_verification'
    CHECK (status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')),
  email_verified_at TIMESTAMPTZ,
  password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
  locked_until TIMESTAMPTZ,
  terms_version TEXT NOT NULL,
  privacy_version TEXT NOT NULL,
  terms_accepted_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_canonical
  ON users (email_canonical);

CREATE TABLE IF NOT EXISTS organization_memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('viewer', 'analyst', 'reviewer', 'owner', 'admin')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('invited', 'active', 'suspended')),
  invited_by_user_id UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_memberships_user
  ON organization_memberships (user_id, status);

CREATE TABLE IF NOT EXISTS terms_acceptances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  terms_version TEXT NOT NULL,
  privacy_version TEXT NOT NULL,
  accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, terms_version, privacy_version)
);

ALTER TABLE workspaces
  ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id),
  ADD COLUMN IF NOT EXISTS created_by_user_id UUID REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE workspaces
SET organization_id = '00000000-0000-0000-0000-000000000001'
WHERE organization_id IS NULL;

ALTER TABLE workspaces
  ALTER COLUMN organization_id SET DEFAULT ambrosia_current_organization_id(),
  ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE review_packet ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id);

DO $$
DECLARE
  tenant_table TEXT;
  tenant_tables TEXT[] := ARRAY[
    'reviews', 'source_pointers', 'audit_events', 'workflow_runs', 'review_packet',
    'decision_audit', 'metric_snapshot', 'retrieval_event', 'outcome_record',
    'packet_version', 'decision_memory_record', 'packet_audit_chain',
    'packet_audit_head', 'roadmap_plan', 'roadmap_decision', 'roadmap_outcome',
    'release_evidence_packet', 'paper_trade', 'execution_fill', 'audit_export_job',
    'relay_run', 'point_in_time_feature', 'signal_definition', 'backtest_run',
    'market_replay_run', 'platform_release_evidence_packet',
    'signal_lifecycle_snapshot', 'feedback_record_store', 'api_idempotency_record',
    'durable_job', 'execution_replay_guard'
  ];
BEGIN
  FOREACH tenant_table IN ARRAY tenant_tables LOOP
    EXECUTE format(
      'ALTER TABLE %I ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id)',
      tenant_table
    );
    EXECUTE format(
      'UPDATE %I SET organization_id = %L WHERE organization_id IS NULL',
      tenant_table,
      '00000000-0000-0000-0000-000000000001'
    );
    EXECUTE format(
      'ALTER TABLE %I ALTER COLUMN organization_id SET DEFAULT ambrosia_current_organization_id()',
      tenant_table
    );
    EXECUTE format(
      'ALTER TABLE %I ALTER COLUMN organization_id SET NOT NULL',
      tenant_table
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I (organization_id)',
      'idx_' || tenant_table || '_organization',
      tenant_table
    );
  END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS user_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  csrf_hash CHAR(64) NOT NULL,
  user_agent_hash CHAR(64),
  ip_prefix TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  absolute_expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  revoke_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_active
  ON user_sessions (user_id, expires_at DESC) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_invitations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email_canonical TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('viewer', 'analyst', 'reviewer', 'admin')),
  token_hash CHAR(64) NOT NULL UNIQUE,
  invited_by_user_id UUID NOT NULL REFERENCES users(id),
  expires_at TIMESTAMPTZ NOT NULL,
  accepted_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_organization_invitations_org
  ON organization_invitations (organization_id, created_at DESC);

CREATE TABLE IF NOT EXISTS guided_samples (
  id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK (version >= 1),
  title TEXT NOT NULL,
  artifact JSONB NOT NULL,
  source_cutoff TIMESTAMPTZ NOT NULL,
  published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, version)
);

INSERT INTO guided_samples (id, version, title, artifact, source_cutoff)
VALUES (
  'ambrosia-first-decision',
  1,
  'Guided decision: challenge a crowded AI infrastructure thesis',
  '{"mode":"demo","dataLabel":"Dated guided sample - not live market data","ticker":"SAMPLE","thesis":"A crowded AI infrastructure position deserves a governed disconfirmation review before capital is committed.","strongestDisagreement":"Consensus demand expectations may already be embedded in price and capex forecasts.","requiredEvidence":["point-in-time demand evidence","valuation sensitivity","liquidity and concentration limits"],"nextAction":"Run the evidence and disconfirmation workflow, then record a human decision."}'::jsonb,
  '2026-08-07T00:00:00Z'
)
ON CONFLICT (id, version) DO UPDATE SET
  title = EXCLUDED.title,
  artifact = EXCLUDED.artifact,
  source_cutoff = EXCLUDED.source_cutoff;

CREATE TABLE IF NOT EXISTS workspace_guided_samples (
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  sample_id TEXT NOT NULL,
  sample_version INTEGER NOT NULL,
  attached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, sample_id, sample_version),
  FOREIGN KEY (sample_id, sample_version) REFERENCES guided_samples(id, version)
);

CREATE TABLE IF NOT EXISTS auth_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  request_id TEXT,
  ip_prefix TEXT,
  user_agent_hash CHAR(64),
  detail JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_events_user_time
  ON auth_events (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS local_worker_credentials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_local_worker_credentials_org
  ON local_worker_credentials (organization_id, status);

CREATE TABLE IF NOT EXISTS llm_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id),
  workspace_id UUID REFERENCES workspaces(id),
  packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  task_type TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued', 'claimed', 'completed', 'failed', 'cancelled')),
  input_payload JSONB NOT NULL,
  observation_cutoff TIMESTAMPTZ,
  claimed_by UUID REFERENCES local_worker_credentials(id),
  claimed_at TIMESTAMPTZ,
  lease_expires_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_jobs_claim
  ON llm_jobs (organization_id, state, created_at) WHERE state = 'queued';

CREATE TABLE IF NOT EXISTS llm_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id),
  job_id UUID REFERENCES llm_jobs(id) ON DELETE SET NULL,
  workspace_id UUID REFERENCES workspaces(id),
  packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE SET NULL,
  workflow_stage TEXT NOT NULL,
  provider_mode_requested TEXT NOT NULL,
  provider_used TEXT NOT NULL,
  fallback_path TEXT,
  model_name TEXT NOT NULL,
  model_digest TEXT,
  ollama_version TEXT,
  worker_id UUID REFERENCES local_worker_credentials(id) ON DELETE SET NULL,
  prompt_template_id TEXT NOT NULL,
  evidence_pack_hash CHAR(64) NOT NULL,
  observation_cutoff TIMESTAMPTZ,
  parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  seed INTEGER,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL,
  total_duration_ns BIGINT,
  load_duration_ns BIGINT,
  prompt_eval_count INTEGER,
  prompt_eval_duration_ns BIGINT,
  eval_count INTEGER,
  eval_duration_ns BIGINT,
  output_schema_version TEXT NOT NULL,
  parse_status TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  raw_artifact_pointer TEXT,
  structured_output JSONB NOT NULL,
  content_hash CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_runs_packet_time
  ON llm_runs (organization_id, packet_id, created_at DESC);

CREATE TABLE IF NOT EXISTS llm_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id),
  run_id UUID NOT NULL REFERENCES llm_runs(id) ON DELETE CASCADE,
  suite_id TEXT NOT NULL,
  suite_version TEXT NOT NULL,
  evaluator_type TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  uncertainty JSONB,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_human_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id),
  run_id UUID NOT NULL REFERENCES llm_runs(id) ON DELETE CASCADE,
  reviewer_user_id UUID NOT NULL REFERENCES users(id),
  disposition TEXT NOT NULL,
  corrections JSONB NOT NULL DEFAULT '{}'::jsonb,
  unsupported_claim_count INTEGER NOT NULL DEFAULT 0,
  citation_issue_count INTEGER NOT NULL DEFAULT 0,
  usefulness_score INTEGER CHECK (usefulness_score BETWEEN 1 AND 5),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL CHECK (event_type IN (
    'onboarding_viewed', 'guided_started', 'own_thesis_started',
    'packet_saved', 'review_completed', 'outcome_recorded', 'return_session'
  )),
  surface TEXT NOT NULL CHECK (char_length(surface) BETWEEN 1 AND 80),
  object_reference_hash CHAR(64),
  event_key TEXT,
  properties JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (event_key IS NULL OR char_length(event_key) BETWEEN 8 AND 120)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_events_org_key
  ON product_events (organization_id, event_key) WHERE event_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_product_events_org_time
  ON product_events (organization_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS artifact_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('exports', 'evidence', 'llm', 'reports')),
  object_reference_hash CHAR(64) NOT NULL,
  storage_key TEXT NOT NULL,
  content_hash CHAR(64) NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
  storage_status TEXT NOT NULL CHECK (storage_status IN ('pending', 'durable', 'failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, storage_key)
);

CREATE INDEX IF NOT EXISTS idx_artifact_records_org_created
  ON artifact_records (organization_id, created_at DESC);

DO $$
DECLARE
  tenant_table TEXT;
  tenant_tables TEXT[] := ARRAY[
    'workspaces', 'reviews', 'source_pointers', 'audit_events', 'workflow_runs',
    'review_packet', 'decision_audit', 'metric_snapshot', 'retrieval_event',
    'outcome_record', 'packet_version', 'decision_memory_record',
    'packet_audit_chain', 'packet_audit_head', 'roadmap_plan', 'roadmap_decision',
    'roadmap_outcome', 'release_evidence_packet', 'paper_trade', 'execution_fill',
    'audit_export_job', 'relay_run', 'point_in_time_feature', 'signal_definition',
    'backtest_run', 'market_replay_run', 'platform_release_evidence_packet',
    'signal_lifecycle_snapshot', 'feedback_record_store', 'api_idempotency_record',
    'durable_job', 'execution_replay_guard',
    'workspace_guided_samples', 'auth_events',
    'llm_jobs', 'llm_runs', 'llm_evaluations',
    'llm_human_reviews', 'product_events', 'artifact_records'
  ];
BEGIN
  FOREACH tenant_table IN ARRAY tenant_tables LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tenant_table);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tenant_table);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (organization_id = ambrosia_current_organization_id()) WITH CHECK (organization_id = ambrosia_current_organization_id())',
      tenant_table
    );
  END LOOP;
END $$;

GRANT USAGE ON SCHEMA public TO ambrosia_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ambrosia_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ambrosia_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ambrosia_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO ambrosia_runtime;

COMMIT;
