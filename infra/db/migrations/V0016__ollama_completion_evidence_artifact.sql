-- Index169: durable completion evidence for adversarial Ollama review.
ALTER TABLE ollama_review_operations
  ADD COLUMN IF NOT EXISTS completion_evidence_artifact_id UUID
    REFERENCES artifact_records(id) ON DELETE SET NULL;