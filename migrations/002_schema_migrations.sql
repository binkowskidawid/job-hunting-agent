-- Ledger of applied migrations. `make migrate` bootstraps this file first, then applies only
-- the migrations this table does not already name, which makes the target safe to re-run.

-- This file is re-run on every `make migrate` to bootstrap the ledger, so its "already
-- exists" notice would print on every single run.
SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- 001 predates the ledger. Where its tables are already present, record it instead of letting
-- `make migrate` re-apply it and fail on an existing relation.
INSERT INTO schema_migrations (filename)
SELECT '001_init.sql'
WHERE to_regclass('public.offer') IS NOT NULL
ON CONFLICT (filename) DO NOTHING;
