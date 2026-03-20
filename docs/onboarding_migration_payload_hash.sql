-- Migration: Add payload_hash and unique index on idempotency_key for onboarding_runs
-- Run this if upgrading from a schema that lacks these columns/indexes.
-- SQLite: multiple NULLs allowed in unique index. PostgreSQL: same.

-- Add payload_hash column (nullable)
ALTER TABLE onboarding_runs ADD COLUMN payload_hash VARCHAR(64) NULL;

-- Add unique index on idempotency_key
-- SQLite/PostgreSQL: multiple NULLs allowed; one value per non-NULL key
CREATE UNIQUE INDEX ix_onboarding_runs_idempotency_key ON onboarding_runs (idempotency_key);
