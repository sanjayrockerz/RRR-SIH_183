-- Phase 3: append-only hybrid investigation intelligence snapshots.
CREATE TABLE IF NOT EXISTS hybrid_intelligence_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  ruleset_version TEXT NOT NULL,
  priority TEXT NOT NULL CHECK (priority IN ('P1','P2','P3')),
  recommendation_text TEXT NOT NULL,
  reason_codes_json JSONB NOT NULL DEFAULT '[]',
  signal_summary_json JSONB NOT NULL DEFAULT '{}',
  evidence_refs_json JSONB NOT NULL DEFAULT '[]',
  limitations_json JSONB NOT NULL DEFAULT '[]',
  previous_priority TEXT,
  priority_changed BOOLEAN NOT NULL DEFAULT FALSE,
  state_hash TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(case_id, state_hash)
);
CREATE INDEX IF NOT EXISTS idx_hybrid_intelligence_case_generated ON hybrid_intelligence_snapshots(case_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_hybrid_intelligence_priority ON hybrid_intelligence_snapshots(priority);
CREATE INDEX IF NOT EXISTS idx_hybrid_intelligence_state_hash ON hybrid_intelligence_snapshots(state_hash);

CREATE OR REPLACE FUNCTION prevent_hybrid_intelligence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'hybrid_intelligence_snapshots is append-only'; END; $$;
DROP TRIGGER IF EXISTS hybrid_intelligence_snapshots_append_only ON hybrid_intelligence_snapshots;
CREATE TRIGGER hybrid_intelligence_snapshots_append_only BEFORE UPDATE OR DELETE ON hybrid_intelligence_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_hybrid_intelligence_mutation();
