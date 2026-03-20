-- Migration: Add created_entities for traceability run-to-entities
-- Run this if upgrading from a schema that lacks this column.

ALTER TABLE onboarding_runs ADD COLUMN created_entities TEXT NULL;
