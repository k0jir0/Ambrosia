-- Index162: immutable LLM proposals and exactly-once packet admission.
CREATE TABLE IF NOT EXISTS llm_packet_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  operation_id UUID NOT NULL UNIQUE REFERENCES ollama_review_operations(id) ON DELETE CASCADE,
  run_id UUID NOT NULL REFERENCES llm_runs(id) ON DELETE CASCADE,
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  base_packet_version INTEGER NOT NULL CHECK (base_packet_version >= 1),
  base_packet_hash CHAR(64) NOT NULL,
  evidence_pack_hash CHAR(64) NOT NULL,
  model_name TEXT NOT NULL,
  model_digest TEXT NOT NULL,
  worker_id UUID REFERENCES local_worker_credentials(id) ON DELETE SET NULL,
  pipeline_version TEXT NOT NULL,
  prompt_template_id TEXT NOT NULL,
  output_schema_version TEXT NOT NULL,
  original_output_hash CHAR(64) NOT NULL,
  proposed_patch_hash CHAR(64) NOT NULL,
  original_output JSONB NOT NULL,
  proposed_patch JSONB NOT NULL,
  deterministic_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  admission_state TEXT NOT NULL CHECK (admission_state IN
    ('proposed','auto_admitted','awaiting_human_review','human_admitted',
     'corrected_and_admitted','rejected','stale')),
  result_packet_version INTEGER,
  admitted_at TIMESTAMPTZ,
  admitted_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_proposal_admissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL REFERENCES llm_packet_proposals(id) ON DELETE CASCADE,
  reviewer_user_id TEXT NOT NULL,
  idempotency_key_hash CHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  disposition TEXT NOT NULL CHECK (disposition IN ('accepted','corrected','rejected')),
  claim_decisions JSONB NOT NULL DEFAULT '[]'::jsonb,
  rationale TEXT NOT NULL,
  result_packet_version INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, reviewer_user_id, idempotency_key_hash),
  UNIQUE (proposal_id, result_packet_version)
);

ALTER TABLE ollama_review_operations
  ADD COLUMN IF NOT EXISTS proposal_id UUID REFERENCES llm_packet_proposals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS admission_state TEXT;

CREATE INDEX IF NOT EXISTS idx_llm_packet_proposals_review
  ON llm_packet_proposals(organization_id, admission_state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_packet_proposals_packet
  ON llm_packet_proposals(organization_id, packet_id, created_at DESC);

ALTER TABLE llm_packet_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_proposal_admissions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON llm_packet_proposals;
DROP POLICY IF EXISTS tenant_isolation ON llm_proposal_admissions;
CREATE POLICY tenant_isolation ON llm_packet_proposals
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY tenant_isolation ON llm_proposal_admissions
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
GRANT SELECT,INSERT,UPDATE,DELETE ON llm_packet_proposals,llm_proposal_admissions TO ambrosia_runtime;
