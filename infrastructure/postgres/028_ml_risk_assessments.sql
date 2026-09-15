CREATE TABLE IF NOT EXISTS ml_risk_assessments (
  inference_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  wallet_id UUID REFERENCES wallets(wallet_id) ON DELETE SET NULL,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  model_name TEXT NOT NULL DEFAULT 'RRR Ethereum Wallet Behaviour Model V2',
  model_version TEXT NOT NULL,
  feature_schema_version TEXT NOT NULL,
  probability NUMERIC(8,6) NOT NULL CHECK (probability >= 0 AND probability <= 1),
  classification TEXT NOT NULL,
  threshold NUMERIC(8,6) NOT NULL,
  top_features JSONB NOT NULL DEFAULT '[]',
  feature_hash TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  observation_cutoff TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'READY',
  limitations JSONB NOT NULL DEFAULT '[]',
  features JSONB NOT NULL DEFAULT '{}',
  provenance JSONB NOT NULL DEFAULT '{}'
);
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS observation_cutoff TIMESTAMPTZ;
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS model_name TEXT NOT NULL DEFAULT 'RRR Ethereum Wallet Behaviour Model V2';
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'READY';
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS limitations JSONB NOT NULL DEFAULT '[]';
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS features JSONB NOT NULL DEFAULT '{}';
ALTER TABLE ml_risk_assessments ADD COLUMN IF NOT EXISTS provenance JSONB NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_ml_risk_case ON ml_risk_assessments(case_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_risk_wallet ON ml_risk_assessments(chain, address, generated_at DESC);

CREATE OR REPLACE FUNCTION prevent_ml_risk_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ml_risk_assessments is append-only';
END; $$;
DROP TRIGGER IF EXISTS ml_risk_assessments_append_only ON ml_risk_assessments;
CREATE TRIGGER ml_risk_assessments_append_only
  BEFORE UPDATE OR DELETE ON ml_risk_assessments
  FOR EACH ROW EXECUTE FUNCTION prevent_ml_risk_mutation();
