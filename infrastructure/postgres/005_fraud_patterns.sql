CREATE TABLE IF NOT EXISTS pattern_observations (
  pattern_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  trace_id UUID NOT NULL REFERENCES trace_runs(trace_id) ON DELETE CASCADE,
  pattern_type TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence_level TEXT NOT NULL,
  confidence_score NUMERIC,
  severity TEXT NOT NULL,
  description TEXT NOT NULL,
  explanation TEXT NOT NULL,
  first_observed_at TIMESTAMPTZ,
  last_observed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  fingerprint TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pattern_observation_evidence (
  pattern_id UUID NOT NULL REFERENCES pattern_observations(pattern_id) ON DELETE CASCADE,
  evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
  PRIMARY KEY (pattern_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_pattern_observations_case ON pattern_observations(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pattern_observations_trace ON pattern_observations(trace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pattern_observations_type ON pattern_observations(pattern_type);
CREATE INDEX IF NOT EXISTS idx_pattern_observations_severity ON pattern_observations(severity);
CREATE INDEX IF NOT EXISTS idx_pattern_observations_fingerprint ON pattern_observations(fingerprint);
CREATE INDEX IF NOT EXISTS idx_pattern_observation_evidence_evidence ON pattern_observation_evidence(evidence_id);
