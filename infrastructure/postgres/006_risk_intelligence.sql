CREATE TABLE IF NOT EXISTS risk_assessments (
  assessment_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  trace_id UUID NOT NULL REFERENCES trace_runs(trace_id) ON DELETE RESTRICT,
  subject_id TEXT NOT NULL,
  subject_chain TEXT NOT NULL,
  subject_address TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  version INTEGER NOT NULL CHECK (version > 0),
  score NUMERIC(6,2) NOT NULL CHECK (score >= 0 AND score <= 100),
  risk_band TEXT NOT NULL,
  investigative_priority TEXT NOT NULL,
  priority_reason TEXT NOT NULL,
  watch_status TEXT NOT NULL,
  calculation_version TEXT NOT NULL,
  calculated_at TIMESTAMPTZ NOT NULL,
  explanation TEXT NOT NULL,
  previous_assessment_id UUID REFERENCES risk_assessments(assessment_id),
  previous_score NUMERIC(6,2),
  score_delta NUMERIC(6,2),
  delta_metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE(case_id,subject_id,version)
);

CREATE TABLE IF NOT EXISTS risk_factors (
  factor_id UUID PRIMARY KEY,
  assessment_id UUID NOT NULL REFERENCES risk_assessments(assessment_id) ON DELETE CASCADE,
  definition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  contribution NUMERIC(6,2) NOT NULL CHECK (contribution >= 0),
  max_contribution NUMERIC(6,2) NOT NULL,
  explanation TEXT NOT NULL,
  confidence_level TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE(assessment_id,definition_id)
);

CREATE TABLE IF NOT EXISTS risk_factor_evidence (
  factor_id UUID NOT NULL REFERENCES risk_factors(factor_id) ON DELETE CASCADE,
  evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
  PRIMARY KEY(factor_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS risk_assessment_patterns (
  assessment_id UUID NOT NULL REFERENCES risk_assessments(assessment_id) ON DELETE CASCADE,
  pattern_id UUID NOT NULL REFERENCES pattern_observations(pattern_id) ON DELETE RESTRICT,
  PRIMARY KEY(assessment_id,pattern_id)
);
CREATE TABLE IF NOT EXISTS risk_assessment_entities (
  assessment_id UUID NOT NULL REFERENCES risk_assessments(assessment_id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,
  PRIMARY KEY(assessment_id,entity_id)
);
CREATE TABLE IF NOT EXISTS risk_assessment_transactions (
  assessment_id UUID NOT NULL REFERENCES risk_assessments(assessment_id) ON DELETE CASCADE,
  transaction_hash TEXT NOT NULL,
  PRIMARY KEY(assessment_id,transaction_hash)
);
CREATE TABLE IF NOT EXISTS risk_factor_patterns (
  factor_id UUID NOT NULL REFERENCES risk_factors(factor_id) ON DELETE CASCADE,
  pattern_id UUID NOT NULL REFERENCES pattern_observations(pattern_id) ON DELETE RESTRICT,
  PRIMARY KEY(factor_id,pattern_id)
);
CREATE TABLE IF NOT EXISTS risk_factor_entities (
  factor_id UUID NOT NULL REFERENCES risk_factors(factor_id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,
  PRIMARY KEY(factor_id,entity_id)
);
CREATE TABLE IF NOT EXISTS risk_factor_transactions (
  factor_id UUID NOT NULL REFERENCES risk_factors(factor_id) ON DELETE CASCADE,
  transaction_hash TEXT NOT NULL,
  PRIMARY KEY(factor_id,transaction_hash)
);

CREATE TABLE IF NOT EXISTS risk_alert_candidates (
  candidate_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  subject_id TEXT NOT NULL,
  assessment_id UUID NOT NULL REFERENCES risk_assessments(assessment_id) ON DELETE CASCADE,
  trigger TEXT NOT NULL,
  severity TEXT NOT NULL,
  risk_delta NUMERIC(6,2) NOT NULL,
  pattern_ids JSONB NOT NULL DEFAULT '[]',
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id UUID PRIMARY KEY,
  case_id UUID REFERENCES cases(case_id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  actor_id TEXT,
  occurred_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_case ON risk_assessments(case_id,calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_subject ON risk_assessments(subject_id,calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_trace ON risk_assessments(trace_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_assessment ON risk_factors(assessment_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_definition ON risk_factors(definition_id);
CREATE INDEX IF NOT EXISTS idx_risk_alert_candidates_case ON risk_alert_candidates(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_case ON audit_events(case_id,occurred_at DESC);
