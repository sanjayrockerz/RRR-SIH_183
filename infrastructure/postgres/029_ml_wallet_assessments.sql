-- Phase 2A: append-only, reproducible wallet-level ML assessment history.
CREATE TABLE IF NOT EXISTS ml_wallet_assessments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  wallet_id UUID REFERENCES wallets(wallet_id) ON DELETE SET NULL,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  normalized_address TEXT NOT NULL,
  model_name TEXT,
  model_version TEXT,
  feature_schema_version TEXT,
  probability NUMERIC(8,6) CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1)),
  classification TEXT,
  threshold NUMERIC(8,6) CHECK (threshold IS NULL OR (threshold >= 0 AND threshold <= 1)),
  feature_hash TEXT,
  features_json JSONB NOT NULL DEFAULT '{}',
  top_features_json JSONB NOT NULL DEFAULT '[]',
  observation_time TIMESTAMPTZ,
  generated_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  limitations_json JSONB NOT NULL DEFAULT '[]',
  model_sha256 TEXT,
  metadata_sha256 TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ml_wallet_assessments_case_generated
  ON ml_wallet_assessments(case_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_wallet_assessments_wallet_generated
  ON ml_wallet_assessments(chain, normalized_address, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_wallet_assessments_model_version
  ON ml_wallet_assessments(model_version);
CREATE INDEX IF NOT EXISTS idx_ml_wallet_assessments_feature_hash
  ON ml_wallet_assessments(feature_hash);

CREATE OR REPLACE FUNCTION prevent_ml_wallet_assessment_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ml_wallet_assessments is append-only';
END; $$;
DROP TRIGGER IF EXISTS ml_wallet_assessments_append_only ON ml_wallet_assessments;
CREATE TRIGGER ml_wallet_assessments_append_only
  BEFORE UPDATE OR DELETE ON ml_wallet_assessments
  FOR EACH ROW EXECUTE FUNCTION prevent_ml_wallet_assessment_mutation();
