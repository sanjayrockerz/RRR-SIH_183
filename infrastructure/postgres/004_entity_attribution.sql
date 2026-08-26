CREATE TABLE IF NOT EXISTS entities (
  entity_id UUID PRIMARY KEY, name TEXT NOT NULL, entity_type TEXT NOT NULL,
  legal_name TEXT, jurisdiction TEXT, website TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS attribution_sources (
  source_id UUID PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL,
  publisher TEXT, reference TEXT NOT NULL, reliability_level TEXT NOT NULL,
  description TEXT, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS address_attributions (
  attribution_id UUID PRIMARY KEY, chain TEXT NOT NULL, address TEXT NOT NULL,
  entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  role TEXT NOT NULL, confidence TEXT NOT NULL, source_id UUID NOT NULL REFERENCES attribution_sources(source_id),
  source_reference TEXT NOT NULL, evidence_id UUID REFERENCES evidence(evidence_id),
  first_seen TIMESTAMPTZ, last_verified TIMESTAMPTZ, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(chain,address,entity_id,role,source_id)
);
CREATE INDEX IF NOT EXISTS idx_address_attributions_lookup ON address_attributions(chain,address);
CREATE INDEX IF NOT EXISTS idx_address_attributions_entity ON address_attributions(entity_id);
CREATE INDEX IF NOT EXISTS idx_address_attributions_source ON address_attributions(source_id);
CREATE INDEX IF NOT EXISTS idx_address_attributions_confidence ON address_attributions(confidence);
