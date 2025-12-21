-- Migration: 004_add_external_tokens_unique.sql
-- Adds a unique constraint on (tenant_id, provider) for external_tokens.
-- IMPORTANT: Before applying this migration in production, ensure there are no
-- duplicate rows (same tenant_id + provider). The included cleanup SQL keeps
-- the most recently updated row and deletes older duplicates.

BEGIN;

-- Example cleanup (run manually after reviewing results):
-- WITH ranked AS (
--   SELECT id, tenant_id, provider,
--     ROW_NUMBER() OVER (PARTITION BY tenant_id, provider ORDER BY updated_at DESC, id DESC) AS rn
--   FROM external_tokens
-- )
-- DELETE FROM external_tokens
-- WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Create the unique constraint
ALTER TABLE external_tokens
ADD CONSTRAINT external_tokens_tenant_provider_unique UNIQUE (tenant_id, provider);

COMMIT;

-- Notes:
-- 1) Run the SELECT query below to detect duplicates before applying the migration:
-- SELECT tenant_id, provider, count(*) as cnt
-- FROM external_tokens
-- GROUP BY tenant_id, provider
-- HAVING count(*) > 1
-- ORDER BY cnt DESC;
