-- Ambrosia DB migration baseline
-- Version: v0001
-- Purpose: baseline schema used by infra/db/init.sql bootstrap

-- NOTE:
-- This baseline intentionally references init.sql as the source-of-truth snapshot
-- for initial deployment bootstrap. Future schema changes must be incremental
-- migrations (V0002+, V0003+, ...) and should not rewrite baseline history.
