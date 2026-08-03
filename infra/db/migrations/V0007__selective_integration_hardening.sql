-- Selective integration hardening: immutable packet versions, durable outcome memory,
-- and a per-packet tamper-evident audit chain.

CREATE TABLE IF NOT EXISTS packet_version (
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  packet_version INTEGER NOT NULL CHECK (packet_version >= 1),
  schema_version TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  content_hash CHAR(64) NOT NULL,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (packet_id, packet_version)
);

CREATE INDEX IF NOT EXISTS idx_packet_version_created
  ON packet_version (packet_id, created_at DESC);

CREATE TABLE IF NOT EXISTS decision_memory_record (
  memory_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  packet_version INTEGER NOT NULL CHECK (packet_version >= 1),
  record_type TEXT NOT NULL CHECK (record_type IN ('checkpoint', 'resolution')),
  outcome TEXT NOT NULL,
  score INTEGER CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
  sequence_id INTEGER NOT NULL CHECK (sequence_id >= 1),
  observed_at TIMESTAMPTZ,
  previous_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL UNIQUE,
  artifact JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (packet_id, sequence_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_memory_packet_created
  ON decision_memory_record (packet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_memory_resolution
  ON decision_memory_record (record_type, observed_at DESC)
  WHERE record_type = 'resolution';

CREATE TABLE IF NOT EXISTS packet_audit_chain (
  packet_id TEXT NOT NULL REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  sequence_id INTEGER NOT NULL CHECK (sequence_id >= 1),
  packet_version INTEGER NOT NULL CHECK (packet_version >= 1),
  event_type TEXT NOT NULL,
  detail TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  payload_hash CHAR(64) NOT NULL,
  previous_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL UNIQUE,
  PRIMARY KEY (packet_id, sequence_id)
);

CREATE INDEX IF NOT EXISTS idx_packet_audit_chain_time
  ON packet_audit_chain (packet_id, event_time DESC);

CREATE TABLE IF NOT EXISTS packet_audit_head (
  packet_id TEXT PRIMARY KEY REFERENCES review_packet(packet_id) ON DELETE CASCADE,
  last_sequence INTEGER NOT NULL CHECK (last_sequence >= 1),
  last_event_hash CHAR(64) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
