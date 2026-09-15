CREATE TABLE IF NOT EXISTS threat_intel_observations (
  observation_id UUID PRIMARY KEY,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT NOT NULL,
  indicator TEXT NOT NULL,
  match_type TEXT NOT NULL,
  confidence DOUBLE PRECISION,
  reference TEXT,
  retrieved_at TIMESTAMPTZ NOT NULL,
  raw_status TEXT NOT NULL,
  case_id UUID REFERENCES cases(case_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_threat_intel_chain_address ON threat_intel_observations(chain, address);
CREATE INDEX IF NOT EXISTS idx_threat_intel_case ON threat_intel_observations(case_id);
CREATE INDEX IF NOT EXISTS idx_threat_intel_source ON threat_intel_observations(source);

CREATE TABLE IF NOT EXISTS recommendation_snapshots (
  recommendation_id UUID PRIMARY KEY,
  snapshot_id UUID NOT NULL,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  ruleset_version TEXT NOT NULL,
  priority TEXT NOT NULL,
  code TEXT NOT NULL,
  title TEXT NOT NULL,
  reason TEXT NOT NULL,
  evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  action_target TEXT,
  generated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recommendation_case_snapshot ON recommendation_snapshots(case_id, snapshot_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_priority ON recommendation_snapshots(priority);
