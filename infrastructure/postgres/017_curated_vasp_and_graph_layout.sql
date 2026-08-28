CREATE TABLE IF NOT EXISTS case_graph_layouts (
  case_id UUID PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
  node_positions JSONB NOT NULL DEFAULT '{}'::jsonb,
  viewport JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO attribution_sources (source_id,name,source_type,publisher,reference,reliability_level,description,created_at,dataset_version)
VALUES ('10000000-0000-0000-0000-000000000001','RRR Development Curated VASP Dataset','CURATED_DATASET','RRR Development','data/intelligence/vasps/vasp-addresses.json','HIGH','Development-only, source-labelled address attribution fixture. It is not commercial or live intelligence.',now(),'2026-08-development')
ON CONFLICT (source_id) DO UPDATE SET dataset_version=EXCLUDED.dataset_version,description=EXCLUDED.description;

INSERT INTO entities (entity_id,name,entity_type,metadata,created_at,updated_at)
VALUES ('10000000-0000-0000-0000-000000000002','Example Exchange — Development Attribution','VASP','{"intelligence_mode":"CURATED_INTELLIGENCE","development_only":true}',now(),now())
ON CONFLICT (entity_id) DO UPDATE SET metadata=EXCLUDED.metadata,updated_at=now();

INSERT INTO address_attributions (attribution_id,chain,address,entity_id,role,confidence,source_id,source_reference,metadata,created_at,updated_at)
VALUES ('10000000-0000-0000-0000-000000000003','ethereum','0x9999999999999999999999999999999999999999','10000000-0000-0000-0000-000000000002','DEPOSIT','HIGH','10000000-0000-0000-0000-000000000001','Development synthetic scenario destination','{"mode":"DEVELOPMENT_SYNTHETIC","dataset_version":"2026-08-development"}',now(),now())
ON CONFLICT (chain,address,entity_id,role,source_id) DO UPDATE SET confidence=EXCLUDED.confidence,metadata=EXCLUDED.metadata,updated_at=now();
