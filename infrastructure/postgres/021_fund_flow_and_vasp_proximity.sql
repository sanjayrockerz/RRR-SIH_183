-- Migration 021: Fund Flow Tracking & VASP Proximity Engine
-- Schema additions for fund flow accounting, VASP exposure metrics, and proximity rankings.

CREATE TABLE IF NOT EXISTS case_fund_flows (
    case_id UUID PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
    total_victim_loss NUMERIC(38, 18) NOT NULL DEFAULT 0,
    traced_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    unresolved_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    vasp_linked_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    mixer_linked_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    bridge_linked_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    intermediary_held_amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    asset_breakdown JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_vasp_exposures (
    exposure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    amount NUMERIC(38, 18) NOT NULL DEFAULT 0,
    asset TEXT NOT NULL DEFAULT 'ETH',
    normalized_value_usd NUMERIC(38, 2) NOT NULL DEFAULT 0,
    percentage_of_victim_funds NUMERIC(5, 2) NOT NULL DEFAULT 0,
    min_hop_distance INT NOT NULL DEFAULT 1,
    first_observed TIMESTAMPTZ,
    last_observed TIMESTAMPTZ,
    attribution_confidence NUMERIC(3, 2) NOT NULL DEFAULT 0,
    classification TEXT NOT NULL DEFAULT 'PROBABLE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_case_vasp_exposure UNIQUE (case_id, entity_id, asset)
);

CREATE TABLE IF NOT EXISTS case_vasp_proximity_rankings (
    ranking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    relevance_score NUMERIC(5, 4) NOT NULL DEFAULT 0,
    attribution_confidence NUMERIC(3, 2) NOT NULL DEFAULT 0,
    amount TEXT NOT NULL DEFAULT '0',
    percentage_of_victim_funds NUMERIC(5, 2) NOT NULL DEFAULT 0,
    hop_distance INT NOT NULL DEFAULT 1,
    time_to_vasp_seconds FLOAT,
    supporting_tx_hashes JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_case_vasp_proximity UNIQUE (case_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_case_vasp_exposures_case_id ON case_vasp_exposures(case_id);
CREATE INDEX IF NOT EXISTS idx_case_vasp_proximity_case_id ON case_vasp_proximity_rankings(case_id);
