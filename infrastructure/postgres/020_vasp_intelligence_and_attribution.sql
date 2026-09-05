-- Migration 020: Persistent VASP Intelligence Registry, Address Clusters, and Attribution Evidence

CREATE TABLE IF NOT EXISTS vasp_entities (
    id VARCHAR(128) PRIMARY KEY,
    legal_name VARCHAR(255) NOT NULL,
    trading_name VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(100),
    website VARCHAR(255),
    regulatory_status VARCHAR(100) DEFAULT 'UNKNOWN',
    entity_type VARCHAR(64) NOT NULL DEFAULT 'VASP',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS address_clusters (
    id VARCHAR(128) PRIMARY KEY,
    chain VARCHAR(32) NOT NULL,
    entity_id VARCHAR(128) REFERENCES vasp_entities(id) ON DELETE SET NULL,
    cluster_type VARCHAR(64) NOT NULL DEFAULT 'DEPOSIT_CLUSTER',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    provenance TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vasp_blockchain_addresses (
    id VARCHAR(128) PRIMARY KEY,
    chain VARCHAR(32) NOT NULL,
    address VARCHAR(255) NOT NULL,
    entity_id VARCHAR(128) REFERENCES vasp_entities(id) ON DELETE CASCADE,
    address_type VARCHAR(64) NOT NULL DEFAULT 'HOT_WALLET',
    cluster_id VARCHAR(128) REFERENCES address_clusters(id) ON DELETE SET NULL,
    source VARCHAR(255) NOT NULL DEFAULT 'CURATED_REGISTRY',
    provenance TEXT NOT NULL DEFAULT 'Source-backed curated intelligence',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.9,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_vasp_blockchain_addresses UNIQUE (chain, address, entity_id)
);

CREATE TABLE IF NOT EXISTS attribution_evidence_records (
    id VARCHAR(128) PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    entity_id VARCHAR(128) NOT NULL REFERENCES vasp_entities(id) ON DELETE CASCADE,
    evidence_type VARCHAR(64) NOT NULL,
    evidence_description TEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transaction_hash VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast address & entity lookup
CREATE INDEX IF NOT EXISTS idx_vasp_addresses_lookup ON vasp_blockchain_addresses (chain, LOWER(address));
CREATE INDEX IF NOT EXISTS idx_vasp_addresses_entity ON vasp_blockchain_addresses (entity_id);
CREATE INDEX IF NOT EXISTS idx_vasp_addresses_cluster ON vasp_blockchain_addresses (cluster_id);
CREATE INDEX IF NOT EXISTS idx_address_clusters_lookup ON address_clusters (chain, entity_id);
CREATE INDEX IF NOT EXISTS idx_attribution_evidence_addr ON attribution_evidence_records (LOWER(address));
CREATE INDEX IF NOT EXISTS idx_attribution_evidence_entity ON attribution_evidence_records (entity_id);

-- Seed Synthetic VASP Demo Intelligence (Marked clearly as DEMO DATA)
INSERT INTO vasp_entities (id, legal_name, trading_name, jurisdiction, website, regulatory_status, entity_type, metadata)
VALUES
    ('vasp-demo-binance', 'Binance Holdings Ltd', 'Binance Global (DEMO DATA)', 'Cayman Islands', 'https://binance.com', 'REGISTERED', 'VASP', '{"is_demo": true, "note": "DEMO DATA ONLY - Not legal proof"}'::jsonb),
    ('vasp-demo-kraken', 'Payward Inc.', 'Kraken Exchange (DEMO DATA)', 'United States', 'https://kraken.com', 'REGISTERED', 'VASP', '{"is_demo": true, "note": "DEMO DATA ONLY - Not legal proof"}'::jsonb),
    ('vasp-demo-coinbase', 'Coinbase Global Inc.', 'Coinbase Custody (DEMO DATA)', 'United States', 'https://coinbase.com', 'REGISTERED', 'VASP', '{"is_demo": true, "note": "DEMO DATA ONLY - Not legal proof"}'::jsonb),
    ('vasp-demo-okx', 'Aux Cayes FinTech Co.', 'OKX Exchange (DEMO DATA)', 'Seychelles', 'https://okx.com', 'REGISTERED', 'VASP', '{"is_demo": true, "note": "DEMO DATA ONLY - Not legal proof"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO address_clusters (id, chain, entity_id, cluster_type, confidence, provenance, metadata)
VALUES
    ('cluster-demo-binance-hot', 'ethereum', 'vasp-demo-binance', 'HOT_WALLET_CLUSTER', 0.95, 'DEMO DATA - Curated Exchange Cluster', '{"is_demo": true}'::jsonb),
    ('cluster-demo-kraken-dep', 'ethereum', 'vasp-demo-kraken', 'DEPOSIT_CLUSTER', 0.92, 'DEMO DATA - Observed Deposit Proxy', '{"is_demo": true}'::jsonb),
    ('cluster-demo-coinbase-vault', 'ethereum', 'vasp-demo-coinbase', 'SWEEP_CLUSTER', 0.96, 'DEMO DATA - Sweep Vault Aggregator', '{"is_demo": true}'::jsonb),
    ('cluster-demo-okx-tron', 'tron', 'vasp-demo-okx', 'HOT_WALLET_CLUSTER', 0.90, 'DEMO DATA - TRON Bridge Aggregator', '{"is_demo": true}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO vasp_blockchain_addresses (id, chain, address, entity_id, address_type, cluster_id, source, provenance, confidence, metadata)
VALUES
    ('addr-demo-binance-1', 'ethereum', '0x28c6c06298d514db089934071355e5743bf21d60', 'vasp-demo-binance', 'HOT_WALLET', 'cluster-demo-binance-hot', 'DEMO_DATASET', 'DEMO DATA - Known Binance Hot Wallet 14', 0.98, '{"is_demo": true}'::jsonb),
    ('addr-demo-binance-2', 'ethereum', '0x21a31ee1afc51d94c2efccaa2092ad1028285549', 'vasp-demo-binance', 'HOT_WALLET', 'cluster-demo-binance-hot', 'DEMO_DATASET', 'DEMO DATA - Known Binance Hot Wallet 15', 0.97, '{"is_demo": true}'::jsonb),
    ('addr-demo-kraken-1', 'ethereum', '0x2910543af39aba0cd09bfb2650210b2d86da3536', 'vasp-demo-kraken', 'DEPOSIT_PROXY', 'cluster-demo-kraken-dep', 'DEMO_DATASET', 'DEMO DATA - Kraken Deposit Proxy', 0.94, '{"is_demo": true}'::jsonb),
    ('addr-demo-coinbase-1', 'ethereum', '0x71660c4005ba85c37ccec55d0c4493e66fe775d3', 'vasp-demo-coinbase', 'SWEEP_VAULT', 'cluster-demo-coinbase-vault', 'DEMO_DATASET', 'DEMO DATA - Coinbase Sweep Vault', 0.96, '{"is_demo": true}'::jsonb),
    ('addr-demo-okx-tron-1', 'tron', 'TYDzsYawMuJF93wYo9V3Biq7rB2nKfyb5j', 'vasp-demo-okx', 'HOT_WALLET', 'cluster-demo-okx-tron', 'DEMO_DATASET', 'DEMO DATA - OKX TRON Hot Wallet', 0.93, '{"is_demo": true}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO attribution_evidence_records (id, address, entity_id, evidence_type, evidence_description, source, confidence, observed_at, metadata)
VALUES
    ('ev-demo-1', '0x28c6c06298d514db089934071355e5743bf21d60', 'vasp-demo-binance', 'KNOWN_ADDRESS', 'Direct match in public VASP database (DEMO DATA)', 'Curated VASP Registry', 0.98, CURRENT_TIMESTAMP, '{"is_demo": true}'::jsonb),
    ('ev-demo-2', '0x2910543af39aba0cd09bfb2650210b2d86da3536', 'vasp-demo-kraken', 'DEPOSIT_ADDRESS_PATTERN', 'Observed high fan-in deposit structure to Kraken proxy (DEMO DATA)', 'Behavioral Pattern Detector', 0.92, CURRENT_TIMESTAMP, '{"is_demo": true}'::jsonb),
    ('ev-demo-3', '0x71660c4005ba85c37ccec55d0c4493e66fe775d3', 'vasp-demo-coinbase', 'CONSOLIDATION_PATTERN', 'Observed periodic batch consolidation to vault (DEMO DATA)', 'Behavioral Pattern Detector', 0.95, CURRENT_TIMESTAMP, '{"is_demo": true}'::jsonb)
ON CONFLICT (id) DO NOTHING;
