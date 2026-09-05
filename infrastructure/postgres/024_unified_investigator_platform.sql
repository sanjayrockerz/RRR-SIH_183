-- Migration 024: Unified Investigator Platform Tables & Indexes

CREATE TABLE IF NOT EXISTS monitored_wallets (
    wallet_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL,
    address VARCHAR(128) NOT NULL,
    chain VARCHAR(32) NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    source VARCHAR(64) NOT NULL DEFAULT 'INVESTIGATOR',
    monitored_by VARCHAR(64) NOT NULL DEFAULT 'investigator-session',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_event_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_monitored_wallets_case ON monitored_wallets(case_id);
CREATE INDEX IF NOT EXISTS idx_monitored_wallets_addr ON monitored_wallets(chain, address);

CREATE TABLE IF NOT EXISTS vasp_information_packages (
    package_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL,
    receiving_vasp_id VARCHAR(64) NOT NULL,
    receiving_vasp_name VARCHAR(128) NOT NULL,
    attribution_classification VARCHAR(32) NOT NULL,
    attribution_confidence DOUBLE PRECISION NOT NULL,
    fund_exposure_usd DOUBLE PRECISION NOT NULL,
    content JSONB NOT NULL,
    evidence_ids TEXT[] DEFAULT '{}',
    created_by VARCHAR(64) NOT NULL DEFAULT 'investigator-session',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vasp_packages_case ON vasp_information_packages(case_id);

CREATE TABLE IF NOT EXISTS investigation_action_recommendations (
    action_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    title VARCHAR(128) NOT NULL,
    reason VARCHAR(512) NOT NULL,
    priority VARCHAR(32) NOT NULL DEFAULT 'HIGH',
    evidence_ids TEXT[] DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'RECOMMENDED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_action_recommendations_case ON investigation_action_recommendations(case_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id VARCHAR(64) PRIMARY KEY,
    actor_id VARCHAR(64) NOT NULL DEFAULT 'investigator-session',
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128),
    case_id VARCHAR(64),
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_case ON audit_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_transfers_source ON transfers(chain, source);
CREATE INDEX IF NOT EXISTS idx_transfers_destination ON transfers(chain, destination);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_records(case_id);
