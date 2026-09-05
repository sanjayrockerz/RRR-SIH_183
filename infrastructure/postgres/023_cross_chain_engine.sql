-- Phase 5: Unified Cross-Chain Investigation Engine Migration
-- Stores Bridge Registries, Bridge Contracts, Bridge Routes, Bridge Evidence, and Cross-Chain Links.

CREATE TABLE IF NOT EXISTS bridge_registries (
    bridge_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    protocol VARCHAR(100) NOT NULL,
    provenance VARCHAR(100) DEFAULT 'OFFICIAL_REGISTRY',
    confidence VARCHAR(50) DEFAULT 'CONFIRMED',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bridge_contracts (
    contract_id VARCHAR(128) PRIMARY KEY,
    bridge_id VARCHAR(64) NOT NULL REFERENCES bridge_registries(bridge_id) ON DELETE CASCADE,
    chain VARCHAR(50) NOT NULL,
    address VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) DEFAULT 'DEPOSIT_ROUTER',
    event_signatures JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (bridge_id, chain, address)
);

CREATE TABLE IF NOT EXISTS bridge_routes (
    route_id VARCHAR(128) PRIMARY KEY,
    bridge_id VARCHAR(64) NOT NULL REFERENCES bridge_registries(bridge_id) ON DELETE CASCADE,
    source_chain VARCHAR(50) NOT NULL,
    destination_chain VARCHAR(50) NOT NULL,
    supported_assets JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (bridge_id, source_chain, destination_chain)
);

CREATE TABLE IF NOT EXISTS bridge_evidence (
    evidence_id VARCHAR(128) PRIMARY KEY,
    bridge_id VARCHAR(64) NOT NULL REFERENCES bridge_registries(bridge_id) ON DELETE CASCADE,
    tx_hash VARCHAR(255) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    provenance VARCHAR(255) NOT NULL,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bridge_contracts_chain_addr ON bridge_contracts(chain, address);
CREATE INDEX IF NOT EXISTS idx_bridge_evidence_tx_hash ON bridge_evidence(tx_hash);
