-- Index146 Wave 4: normalized tenant lifecycle persistence for Alpha and Signals.

BEGIN;

CREATE TABLE IF NOT EXISTS alpha_hypothesis (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  hypothesis_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, hypothesis_id)
);

CREATE INDEX IF NOT EXISTS idx_alpha_hypothesis_org_updated
  ON alpha_hypothesis (organization_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_signal (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  signal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  active_version INTEGER NOT NULL DEFAULT 1 CHECK (active_version >= 1),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, signal_id)
);

CREATE INDEX IF NOT EXISTS idx_research_signal_org_status_updated
  ON research_signal (organization_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_signal_version (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  signal_id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK (version >= 1),
  artifact JSONB NOT NULL,
  content_hash CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, signal_id, version),
  FOREIGN KEY (organization_id, signal_id)
    REFERENCES research_signal(organization_id, signal_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS signal_validation_record (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  validation_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  signal_version INTEGER NOT NULL,
  status TEXT NOT NULL,
  evidence_class TEXT NOT NULL DEFAULT 'fixture',
  artifact JSONB NOT NULL,
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (organization_id, validation_id),
  FOREIGN KEY (organization_id, signal_id, signal_version)
    REFERENCES research_signal_version(organization_id, signal_id, version) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_signal_validation_org_signal_time
  ON signal_validation_record (organization_id, signal_id, completed_at DESC);

CREATE TABLE IF NOT EXISTS signal_validation_artifact (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  validation_id TEXT NOT NULL,
  artifact_ref TEXT NOT NULL,
  content_hash CHAR(64),
  content_type TEXT,
  size_bytes BIGINT CHECK (size_bytes IS NULL OR size_bytes >= 0),
  storage_status TEXT NOT NULL DEFAULT 'referenced'
    CHECK (storage_status IN ('referenced', 'pending', 'durable', 'failed', 'revoked')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, validation_id, artifact_ref),
  FOREIGN KEY (organization_id, validation_id)
    REFERENCES signal_validation_record(organization_id, validation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS research_object_snapshot (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  snapshot_id TEXT NOT NULL,
  object_type TEXT NOT NULL CHECK (object_type IN ('alpha_hypothesis', 'signal')),
  object_id TEXT NOT NULL,
  object_version INTEGER,
  content_hash CHAR(64) NOT NULL,
  snapshot JSONB NOT NULL,
  source TEXT,
  data_mode TEXT,
  provider TEXT,
  as_of TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, snapshot_id),
  UNIQUE (organization_id, object_type, object_id, object_version, content_hash)
);

CREATE TABLE IF NOT EXISTS research_review_link (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  link_id TEXT NOT NULL,
  review_id TEXT NOT NULL,
  object_type TEXT NOT NULL CHECK (object_type IN ('alpha_hypothesis', 'signal')),
  object_id TEXT NOT NULL,
  object_version INTEGER,
  snapshot_id TEXT,
  relationship_type TEXT NOT NULL DEFAULT 'research_evidence',
  artifact JSONB NOT NULL,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, link_id),
  UNIQUE (organization_id, review_id, object_type, object_id, object_version),
  FOREIGN KEY (organization_id, snapshot_id)
    REFERENCES research_object_snapshot(organization_id, snapshot_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_research_review_link_org_review
  ON research_review_link (organization_id, review_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_lifecycle_event (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  event_id TEXT NOT NULL,
  object_type TEXT NOT NULL CHECK (object_type IN ('alpha_hypothesis', 'signal')),
  object_id TEXT NOT NULL,
  object_version INTEGER,
  event_type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  actor_subject TEXT,
  reason TEXT,
  evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_research_lifecycle_event_org_object_time
  ON research_lifecycle_event (organization_id, object_type, object_id, created_at DESC);

CREATE TABLE IF NOT EXISTS scanner_promotion (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  promotion_id TEXT NOT NULL,
  candidate_key TEXT NOT NULL,
  scanner_run_id TEXT NOT NULL,
  hypothesis_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  signal_version INTEGER NOT NULL,
  promoted_by_subject TEXT,
  artifact JSONB NOT NULL,
  promoted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, promotion_id),
  UNIQUE (organization_id, candidate_key),
  FOREIGN KEY (organization_id, hypothesis_id)
    REFERENCES alpha_hypothesis(organization_id, hypothesis_id) ON DELETE RESTRICT,
  FOREIGN KEY (organization_id, signal_id, signal_version)
    REFERENCES research_signal_version(organization_id, signal_id, version) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_scanner_promotion_org_time
  ON scanner_promotion (organization_id, promoted_at DESC);

CREATE TABLE IF NOT EXISTS signal_decision_writeback (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  writeback_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  signal_version INTEGER NOT NULL,
  review_id TEXT NOT NULL,
  decision_state TEXT NOT NULL,
  execution_readiness TEXT NOT NULL DEFAULT 'not_executable',
  artifact JSONB NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, writeback_id),
  UNIQUE (organization_id, signal_id, signal_version, review_id),
  FOREIGN KEY (organization_id, signal_id, signal_version)
    REFERENCES research_signal_version(organization_id, signal_id, version) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS signal_outcome_writeback (
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  writeback_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  signal_version INTEGER NOT NULL,
  review_id TEXT NOT NULL,
  outcome_quality TEXT NOT NULL,
  artifact JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, writeback_id),
  UNIQUE (organization_id, signal_id, signal_version, review_id),
  FOREIGN KEY (organization_id, signal_id, signal_version)
    REFERENCES research_signal_version(organization_id, signal_id, version) ON DELETE CASCADE
);

DO $$
DECLARE
  tenant_table TEXT;
  tenant_tables TEXT[] := ARRAY[
    'alpha_hypothesis', 'research_signal', 'research_signal_version',
    'signal_validation_record', 'signal_validation_artifact',
    'research_object_snapshot', 'research_review_link',
    'research_lifecycle_event', 'scanner_promotion',
    'signal_decision_writeback', 'signal_outcome_writeback'
  ];
BEGIN
  FOREACH tenant_table IN ARRAY tenant_tables LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tenant_table);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tenant_table);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tenant_table);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (organization_id = ambrosia_current_organization_id()) WITH CHECK (organization_id = ambrosia_current_organization_id())',
      tenant_table
    );
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON
  alpha_hypothesis, research_signal, research_signal_version,
  signal_validation_record, signal_validation_artifact,
  research_object_snapshot, research_review_link,
  research_lifecycle_event, scanner_promotion,
  signal_decision_writeback, signal_outcome_writeback
TO ambrosia_runtime;

COMMIT;