-- Ambrosia DB migration template
-- Version: v000X
-- File name pattern: V000X__short_description.sql
-- Example: V0002__add_feedback_indexes.sql

BEGIN;

-- 1) Additive changes first (new columns, tables, indexes)
-- ALTER TABLE ... ADD COLUMN ...;

-- 2) Backfill or data migration (idempotent where practical)
-- UPDATE ... WHERE ...;

-- 3) Constraint hardening after backfill
-- ALTER TABLE ... ADD CONSTRAINT ...;

COMMIT;

-- Rollback guidance (document manually in PR if rollback is non-trivial)
