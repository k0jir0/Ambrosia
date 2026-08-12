-- Index156: replace the historical placeholder ticker and persist instrument identity.
BEGIN;

CREATE TABLE IF NOT EXISTS instrument_reference (
  instrument_id TEXT PRIMARY KEY,
  canonical_ticker TEXT NOT NULL UNIQUE,
  exchange TEXT NOT NULL,
  instrument_type TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  verification_provider TEXT NOT NULL,
  provider_instrument_id TEXT NOT NULL,
  verified_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS unresolved_instrument_audit (
  id BIGSERIAL PRIMARY KEY,
  requested_symbol TEXT NOT NULL,
  resolution_status TEXT NOT NULL CHECK (resolution_status IN
    ('inactive', 'ambiguous', 'unsupported', 'not_found', 'provider_unavailable')),
  context TEXT NOT NULL,
  detail JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO instrument_reference (
  instrument_id, canonical_ticker, exchange, instrument_type, active,
  verification_provider, provider_instrument_id, verified_at
) VALUES (
  'yahoo:NVDA', 'NVDA', 'NMS', 'EQUITY', TRUE,
  'yahoo-finance', 'NVDA', '2026-08-12T00:00:00Z'
) ON CONFLICT (instrument_id) DO UPDATE SET
  canonical_ticker = EXCLUDED.canonical_ticker,
  active = EXCLUDED.active,
  verified_at = EXCLUDED.verified_at,
  updated_at = now();

UPDATE guided_samples
SET artifact = jsonb_set(artifact, '{ticker}', '"NVDA"'::jsonb, true)
WHERE upper(coalesce(artifact->>'ticker', '')) IN
  ('SAMPLE', 'DEMO', 'TEST', 'TICKER', 'SYMBOL', 'UNKNOWN', 'UNSPECIFIED');

ALTER TABLE guided_samples DROP CONSTRAINT IF EXISTS guided_samples_real_ticker;
ALTER TABLE guided_samples ADD CONSTRAINT guided_samples_real_ticker CHECK (
  upper(coalesce(artifact->>'ticker', '')) NOT IN
  ('SAMPLE', 'DEMO', 'TEST', 'TICKER', 'SYMBOL', 'UNKNOWN', 'UNSPECIFIED')
);

GRANT SELECT ON instrument_reference TO ambrosia_runtime;
GRANT SELECT, INSERT ON unresolved_instrument_audit TO ambrosia_runtime;
GRANT USAGE, SELECT ON SEQUENCE unresolved_instrument_audit_id_seq TO ambrosia_runtime;

COMMIT;
