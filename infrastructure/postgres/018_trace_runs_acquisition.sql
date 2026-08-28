-- Migration to add acquisition column to trace_runs table
ALTER TABLE trace_runs ADD COLUMN IF NOT EXISTS acquisition JSONB NOT NULL DEFAULT '{}';
