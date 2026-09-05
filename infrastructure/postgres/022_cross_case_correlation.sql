-- Migration 022: Cross-Case Wallet Correlation & Fraud Network Intelligence
-- Supports Phase 4 multi-case infrastructure matching, relationship scoring, and impact tracking.

CREATE TABLE IF NOT EXISTS case_relationships (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    related_case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    relationship_score NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    shared_wallets JSONB NOT NULL DEFAULT '[]'::jsonb,
    shared_transactions JSONB NOT NULL DEFAULT '[]'::jsonb,
    shared_infrastructure JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_case_pair UNIQUE (case_id, related_case_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_case_relationships_case_id ON case_relationships(case_id);
CREATE INDEX IF NOT EXISTS idx_case_relationships_related_case_id ON case_relationships(related_case_id);
CREATE INDEX IF NOT EXISTS idx_case_relationships_type ON case_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_case_relationships_score ON case_relationships(relationship_score DESC);

CREATE TABLE IF NOT EXISTS infrastructure_impact_nodes (
    node_id TEXT PRIMARY KEY,
    chain TEXT NOT NULL DEFAULT 'ethereum',
    node_type TEXT NOT NULL,
    connected_case_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    victim_count INT NOT NULL DEFAULT 0,
    aggregate_exposure_usd NUMERIC(18,4) NOT NULL DEFAULT 0.0,
    first_observed TIMESTAMPTZ,
    last_observed TIMESTAMPTZ,
    provenance_description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_infrastructure_impact_node_type ON infrastructure_impact_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_infrastructure_impact_exposure ON infrastructure_impact_nodes(aggregate_exposure_usd DESC);
