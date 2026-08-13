-- Index162/163 retention closure and Index164 report replay ledger.
ALTER TABLE artifact_records DROP CONSTRAINT IF EXISTS artifact_records_storage_status_check;
ALTER TABLE artifact_records ADD CONSTRAINT artifact_records_storage_status_check
  CHECK (storage_status IN ('pending','durable','failed','deleted'));

ALTER TABLE llm_packet_proposals
  ADD COLUMN IF NOT EXISTS original_output_artifact_id UUID
    REFERENCES artifact_records(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ
    NOT NULL DEFAULT (now() + interval '90 days'),
  ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS deletion_state TEXT NOT NULL DEFAULT 'active'
    CHECK (deletion_state IN ('active','content_deleted'));

CREATE INDEX IF NOT EXISTS idx_llm_packet_proposals_retention
  ON llm_packet_proposals(organization_id,retention_until)
  WHERE deletion_state='active';

CREATE TABLE IF NOT EXISTS report_generation_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  reviewer_user_id TEXT NOT NULL,
  idempotency_key_hash CHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  packet_version INTEGER NOT NULL CHECK (packet_version >= 1),
  state TEXT NOT NULL CHECK (state IN ('pending','completed','failed')),
  report_artifact JSONB,
  artifact_id UUID REFERENCES artifact_records(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id,reviewer_user_id,idempotency_key_hash)
);

ALTER TABLE report_generation_requests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON report_generation_requests;
CREATE POLICY tenant_isolation ON report_generation_requests
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
GRANT SELECT,INSERT,UPDATE,DELETE ON report_generation_requests TO ambrosia_runtime;
