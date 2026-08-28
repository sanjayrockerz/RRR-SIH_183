ALTER TABLE attribution_sources ADD COLUMN IF NOT EXISTS dataset_version TEXT;
CREATE INDEX IF NOT EXISTS idx_attribution_sources_dataset_version ON attribution_sources(dataset_version);
CREATE INDEX IF NOT EXISTS idx_address_attributions_verified ON address_attributions(last_verified DESC);
