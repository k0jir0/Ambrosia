-- Ambrosia DB migration
-- Version: v0002
-- Purpose: durable Index84 Plan/Decision/Outcome roadmap ledger

CREATE TABLE IF NOT EXISTS roadmap_plan (
  plan_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  workstream TEXT NOT NULL,
  owner TEXT NOT NULL DEFAULT 'TBD',
  quality TEXT NOT NULL CHECK (quality IN ('P0', 'P1', 'P2', 'P3', 'P4')),
  status TEXT NOT NULL CHECK (status IN ('proposed', 'scoped', 'active', 'blocked', 'done', 'deferred')),
  target_milestone TEXT,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roadmap_decision (
  decision_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES roadmap_plan(plan_id) ON DELETE CASCADE,
  decision_type TEXT NOT NULL,
  quality TEXT NOT NULL CHECK (quality IN ('D0', 'D1', 'D2', 'D3', 'D4', 'D5')),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roadmap_outcome (
  outcome_id TEXT PRIMARY KEY,
  decision_id TEXT NOT NULL REFERENCES roadmap_decision(decision_id) ON DELETE CASCADE,
  quality TEXT NOT NULL CHECK (quality IN ('O0', 'O1', 'O2', 'O3', 'O4', 'O5')),
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS release_evidence_packet (
  id TEXT PRIMARY KEY,
  roadmap_plan_ids TEXT[] NOT NULL DEFAULT '{}',
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roadmap_plan_status ON roadmap_plan(status);
CREATE INDEX IF NOT EXISTS idx_roadmap_plan_workstream ON roadmap_plan(workstream);
CREATE INDEX IF NOT EXISTS idx_roadmap_decision_plan ON roadmap_decision(plan_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_outcome_decision ON roadmap_outcome(decision_id);