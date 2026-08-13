-- Index163: typed claim lineage, append-only proposal events, and compensating rollback.
ALTER TABLE llm_packet_proposals DROP CONSTRAINT IF EXISTS llm_packet_proposals_admission_state_check;
ALTER TABLE llm_packet_proposals ADD CONSTRAINT llm_packet_proposals_admission_state_check
  CHECK (admission_state IN
    ('proposed','auto_admitted','awaiting_human_review','human_admitted',
     'corrected_and_admitted','rejected','stale','rolled_back'));
ALTER TABLE llm_packet_proposals
  ADD COLUMN IF NOT EXISTS reviewer_decision_hash CHAR(64),
  ADD COLUMN IF NOT EXISTS rollback_packet_version INTEGER;

ALTER TABLE llm_proposal_admissions
  ADD COLUMN IF NOT EXISTS decision_hash CHAR(64),
  ADD COLUMN IF NOT EXISTS unsupported_claim_count INTEGER NOT NULL DEFAULT 0
    CHECK (unsupported_claim_count >= 0),
  ADD COLUMN IF NOT EXISTS citation_issue_count INTEGER NOT NULL DEFAULT 0
    CHECK (citation_issue_count >= 0),
  ADD COLUMN IF NOT EXISTS usefulness_score INTEGER CHECK (usefulness_score BETWEEN 1 AND 5);

CREATE TABLE IF NOT EXISTS llm_proposal_claim_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  admission_id UUID NOT NULL REFERENCES llm_proposal_admissions(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL REFERENCES llm_packet_proposals(id) ON DELETE CASCADE,
  claim_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN
    ('accept_as_proposed','accept_with_human_correction','reject')),
  original_claim_hash CHAR(64) NOT NULL,
  corrected_claim_hash CHAR(64),
  corrected_text TEXT,
  supporting_evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  falsifier TEXT,
  rationale TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (admission_id, claim_id)
);

CREATE TABLE IF NOT EXISTS llm_proposal_events (
  id BIGSERIAL PRIMARY KEY,
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL REFERENCES llm_packet_proposals(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload_hash CHAR(64) NOT NULL,
  previous_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_proposal_rollbacks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id()
    REFERENCES organizations(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL REFERENCES llm_packet_proposals(id) ON DELETE CASCADE,
  reviewer_user_id TEXT NOT NULL,
  idempotency_key_hash CHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  reverted_packet_version INTEGER NOT NULL,
  rollback_packet_version INTEGER NOT NULL,
  rationale TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, reviewer_user_id, idempotency_key_hash),
  UNIQUE (proposal_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_proposal_events
  ON llm_proposal_events(organization_id,proposal_id,id);
CREATE INDEX IF NOT EXISTS idx_llm_claim_decisions
  ON llm_proposal_claim_decisions(organization_id,proposal_id,created_at);

ALTER TABLE llm_proposal_claim_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_proposal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_proposal_rollbacks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON llm_proposal_claim_decisions;
DROP POLICY IF EXISTS tenant_isolation ON llm_proposal_events;
DROP POLICY IF EXISTS tenant_isolation ON llm_proposal_rollbacks;
CREATE POLICY tenant_isolation ON llm_proposal_claim_decisions
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY tenant_isolation ON llm_proposal_events
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY tenant_isolation ON llm_proposal_rollbacks
  USING (organization_id=ambrosia_current_organization_id())
  WITH CHECK (organization_id=ambrosia_current_organization_id());
GRANT SELECT,INSERT,UPDATE,DELETE ON
  llm_proposal_claim_decisions,llm_proposal_events,llm_proposal_rollbacks
  TO ambrosia_runtime;
GRANT USAGE,SELECT ON SEQUENCE llm_proposal_events_id_seq TO ambrosia_runtime;
