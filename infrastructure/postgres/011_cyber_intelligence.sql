CREATE TABLE IF NOT EXISTS cyber_intelligence_sources (
  source_id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  publisher TEXT,
  reference TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  status TEXT NOT NULL,
  retrieved_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(name, dataset_version)
);

CREATE TABLE IF NOT EXISTS threat_indicators (
  indicator_id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES cyber_intelligence_sources(source_id) ON DELETE RESTRICT,
  indicator_type TEXT NOT NULL,
  value TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  chain TEXT,
  confidence TEXT NOT NULL,
  first_observed_at TIMESTAMPTZ,
  last_observed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE(source_id, indicator_type, normalized_value, chain)
);

CREATE TABLE IF NOT EXISTS sanctions_records (
  record_id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES cyber_intelligence_sources(source_id) ON DELETE RESTRICT,
  subject_type TEXT NOT NULL,
  value TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  chain TEXT,
  program TEXT,
  listed_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  confidence TEXT NOT NULL,
  source_reference TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE(source_id, subject_type, normalized_value, chain)
);

CREATE TABLE IF NOT EXISTS contract_security_findings (
  finding_id UUID PRIMARY KEY,
  chain TEXT NOT NULL,
  contract_address TEXT NOT NULL,
  source_id UUID NOT NULL REFERENCES cyber_intelligence_sources(source_id) ON DELETE RESTRICT,
  finding_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  confidence TEXT NOT NULL,
  description TEXT NOT NULL,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  observed_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE(chain, contract_address, source_id, finding_type)
);

CREATE TABLE IF NOT EXISTS screening_runs (
  screening_id UUID PRIMARY KEY,
  case_id UUID REFERENCES cases(case_id) ON DELETE CASCADE,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  outcome TEXT NOT NULL,
  source_status TEXT NOT NULL,
  screened_at TIMESTAMPTZ NOT NULL,
  explanation TEXT NOT NULL,
  limitation TEXT
);

CREATE TABLE IF NOT EXISTS screening_matches (
  screening_id UUID NOT NULL REFERENCES screening_runs(screening_id) ON DELETE CASCADE,
  match_id UUID NOT NULL,
  record_id UUID NOT NULL REFERENCES sanctions_records(record_id) ON DELETE RESTRICT,
  source_id UUID NOT NULL REFERENCES cyber_intelligence_sources(source_id) ON DELETE RESTRICT,
  matched_value TEXT NOT NULL,
  match_type TEXT NOT NULL,
  confidence TEXT NOT NULL,
  explanation TEXT NOT NULL,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  PRIMARY KEY(screening_id, match_id)
);

CREATE INDEX IF NOT EXISTS idx_sanctions_records_lookup ON sanctions_records(chain, normalized_value);
CREATE INDEX IF NOT EXISTS idx_threat_indicators_lookup ON threat_indicators(chain, normalized_value);
CREATE INDEX IF NOT EXISTS idx_screening_runs_case ON screening_runs(case_id, screened_at DESC);
CREATE INDEX IF NOT EXISTS idx_screening_runs_address ON screening_runs(chain, address, screened_at DESC);
CREATE INDEX IF NOT EXISTS idx_contract_security_lookup ON contract_security_findings(chain, contract_address);
