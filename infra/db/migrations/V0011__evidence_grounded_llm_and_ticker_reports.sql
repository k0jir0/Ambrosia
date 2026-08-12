-- Index157 evidence-grounded Ollama processing and ticker intelligence.
ALTER TABLE llm_runs
  ADD COLUMN IF NOT EXISTS pipeline_version TEXT,
  ADD COLUMN IF NOT EXISTS context_builder_version TEXT,
  ADD COLUMN IF NOT EXISTS verifier_model_name TEXT,
  ADD COLUMN IF NOT EXISTS verifier_model_digest TEXT,
  ADD COLUMN IF NOT EXISTS verification_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS rejected_claims JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS repair_lineage JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS finish_reason TEXT,
  ADD COLUMN IF NOT EXISTS truncation_detected BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS stage_hashes JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS llm_evidence_packs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id() REFERENCES organizations(id) ON DELETE CASCADE,
 packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE SET NULL, schema_version TEXT NOT NULL, ticker_identity JSONB NOT NULL,
 observation_cutoff TIMESTAMPTZ NOT NULL, evidence_items JSONB NOT NULL, content_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(organization_id, content_hash));
CREATE TABLE IF NOT EXISTS llm_material_claims (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id() REFERENCES organizations(id) ON DELETE CASCADE,
 run_id UUID REFERENCES llm_runs(id) ON DELETE CASCADE, packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE SET NULL, claim_key TEXT NOT NULL,
 claim_type TEXT NOT NULL, materiality TEXT NOT NULL, claim_text TEXT NOT NULL, uncertainty DOUBLE PRECISION NOT NULL CHECK(uncertainty BETWEEN 0 AND 1),
 falsifier TEXT, admission_status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS llm_claim_evidence_relations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id() REFERENCES organizations(id) ON DELETE CASCADE,
 claim_id UUID NOT NULL REFERENCES llm_material_claims(id) ON DELETE CASCADE, evidence_id TEXT NOT NULL, relation TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS llm_verification_findings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id() REFERENCES organizations(id) ON DELETE CASCADE,
 run_id UUID NOT NULL REFERENCES llm_runs(id) ON DELETE CASCADE, claim_key TEXT NOT NULL, status TEXT NOT NULL, evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
 reasons JSONB NOT NULL DEFAULT '[]'::jsonb, deterministic_checks_passed BOOLEAN NOT NULL, verifier TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ticker_intelligence_reports (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL DEFAULT ambrosia_current_organization_id() REFERENCES organizations(id) ON DELETE CASCADE,
 packet_id TEXT REFERENCES review_packet(packet_id) ON DELETE SET NULL, ticker_identity JSONB NOT NULL, as_of TIMESTAMPTZ NOT NULL, knowledge_cutoff TIMESTAMPTZ NOT NULL,
 schema_version TEXT NOT NULL, pipeline_version TEXT, source_snapshot_hash CHAR(64), verified_claim_coverage DOUBLE PRECISION NOT NULL DEFAULT 0,
 unresolved_material_claim_count INTEGER NOT NULL DEFAULT 0, validation_status TEXT NOT NULL, sections JSONB NOT NULL, calculation_artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
 artifact_hash CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());

ALTER TABLE llm_evidence_packs ENABLE ROW LEVEL SECURITY; ALTER TABLE llm_material_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_claim_evidence_relations ENABLE ROW LEVEL SECURITY; ALTER TABLE llm_verification_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticker_intelligence_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY llm_evidence_packs_tenant ON llm_evidence_packs USING (organization_id=ambrosia_current_organization_id()) WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY llm_material_claims_tenant ON llm_material_claims USING (organization_id=ambrosia_current_organization_id()) WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY llm_claim_evidence_relations_tenant ON llm_claim_evidence_relations USING (organization_id=ambrosia_current_organization_id()) WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY llm_verification_findings_tenant ON llm_verification_findings USING (organization_id=ambrosia_current_organization_id()) WITH CHECK (organization_id=ambrosia_current_organization_id());
CREATE POLICY ticker_intelligence_reports_tenant ON ticker_intelligence_reports USING (organization_id=ambrosia_current_organization_id()) WITH CHECK (organization_id=ambrosia_current_organization_id());
