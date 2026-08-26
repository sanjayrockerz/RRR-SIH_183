CREATE TABLE IF NOT EXISTS chains (
  chain_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  family TEXT NOT NULL,
  native_asset TEXT NOT NULL,
  address_format TEXT NOT NULL,
  explorer_base_url TEXT NOT NULL,
  block_time_seconds NUMERIC NOT NULL,
  finality_model TEXT NOT NULL,
  provider TEXT NOT NULL,
  historical_capability TEXT NOT NULL,
  realtime_capability TEXT NOT NULL,
  token_transfer_capability TEXT NOT NULL,
  bridge_detection_capability TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chain_addresses (
  chain_address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain TEXT NOT NULL REFERENCES chains(chain_id),
  address TEXT NOT NULL,
  wallet_id UUID REFERENCES wallets(wallet_id),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(chain,address)
);
CREATE TABLE IF NOT EXISTS asset_identities (
  asset_identity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain TEXT NOT NULL REFERENCES chains(chain_id),
  contract_address TEXT,
  symbol TEXT NOT NULL,
  decimals INTEGER,
  canonical_asset_id TEXT NOT NULL,
  mapping_source TEXT NOT NULL,
  confidence TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '1',
  UNIQUE(chain,contract_address,canonical_asset_id,version)
);
CREATE TABLE IF NOT EXISTS asset_mappings (
  mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_asset_id UUID NOT NULL REFERENCES asset_identities(asset_identity_id),
  destination_asset_id UUID NOT NULL REFERENCES asset_identities(asset_identity_id),
  confidence TEXT NOT NULL,
  mapping_source TEXT NOT NULL,
  version TEXT NOT NULL,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(source_asset_id,destination_asset_id,version)
);
CREATE TABLE IF NOT EXISTS bridge_definitions (
  bridge_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  supported_chains JSONB NOT NULL,
  deposit_contracts JSONB NOT NULL DEFAULT '{}',
  withdrawal_contracts JSONB NOT NULL DEFAULT '{}',
  router_contracts JSONB NOT NULL DEFAULT '{}',
  token_mappings JSONB NOT NULL DEFAULT '[]',
  event_signatures JSONB NOT NULL DEFAULT '[]',
  confidence_policy TEXT NOT NULL,
  source TEXT NOT NULL,
  version TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS bridge_interactions (
  interaction_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  bridge_id TEXT NOT NULL REFERENCES bridge_definitions(bridge_id),
  interaction_type TEXT NOT NULL,
  source_chain TEXT NOT NULL REFERENCES chains(chain_id),
  destination_chain TEXT REFERENCES chains(chain_id),
  transaction_hash TEXT NOT NULL,
  bridge_contract TEXT NOT NULL,
  source_address TEXT NOT NULL,
  recipient TEXT,
  asset TEXT NOT NULL,
  amount TEXT NOT NULL,
  timestamp TIMESTAMPTZ,
  message_id TEXT,
  nonce TEXT,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  confidence TEXT NOT NULL,
  source TEXT NOT NULL,
  explanation TEXT NOT NULL,
  raw_reference JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(case_id,bridge_id,transaction_hash,interaction_type)
);
CREATE TABLE IF NOT EXISTS cross_chain_links (
  link_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  source_chain TEXT NOT NULL REFERENCES chains(chain_id),
  source_address TEXT NOT NULL,
  destination_chain TEXT REFERENCES chains(chain_id),
  destination_address TEXT,
  source_transaction_hash TEXT NOT NULL,
  destination_transaction_hash TEXT NOT NULL DEFAULT '',
  bridge_id TEXT NOT NULL REFERENCES bridge_definitions(bridge_id),
  correlation_id TEXT NOT NULL,
  correlation_level TEXT NOT NULL,
  confidence_score NUMERIC NOT NULL,
  confidence_band TEXT NOT NULL,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  correlation_reasons JSONB NOT NULL DEFAULT '[]',
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  provenance_source TEXT NOT NULL,
  explanation TEXT NOT NULL,
  observed_or_inferred TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(case_id,correlation_id)
);
CREATE TABLE IF NOT EXISTS cross_chain_link_evidence (
  link_id UUID NOT NULL REFERENCES cross_chain_links(link_id) ON DELETE CASCADE,
  evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
  PRIMARY KEY(link_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS entity_addresses (
  entity_address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  chain TEXT NOT NULL REFERENCES chains(chain_id),
  address TEXT NOT NULL,
  source TEXT NOT NULL,
  confidence TEXT NOT NULL,
  evidence_reference TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(entity_id,chain,address,source)
);
CREATE TABLE IF NOT EXISTS cross_chain_trace_runs (
  trace_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  root_chain TEXT NOT NULL,
  root_address TEXT NOT NULL,
  chains JSONB NOT NULL,
  limits JSONB NOT NULL,
  status TEXT NOT NULL,
  cross_chain_hops INTEGER NOT NULL,
  node_count INTEGER NOT NULL,
  edge_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cross_chain_trace_nodes (
  trace_id UUID NOT NULL REFERENCES cross_chain_trace_runs(trace_id) ON DELETE CASCADE,
  node_id TEXT NOT NULL,
  chain TEXT NOT NULL REFERENCES chains(chain_id),
  address TEXT NOT NULL,
  node_type TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY(trace_id,node_id)
);
CREATE TABLE IF NOT EXISTS cross_chain_trace_edges (
  trace_id UUID NOT NULL REFERENCES cross_chain_trace_runs(trace_id) ON DELETE CASCADE,
  edge_id UUID NOT NULL,
  edge_type TEXT NOT NULL,
  source_node TEXT NOT NULL,
  destination_node TEXT NOT NULL,
  chain TEXT,
  destination_chain TEXT,
  transaction_hash TEXT,
  destination_transaction_hash TEXT,
  asset TEXT,
  amount TEXT,
  timestamp TIMESTAMPTZ,
  bridge_id TEXT,
  link_id UUID,
  confidence_band TEXT,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  observed_or_inferred TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY(trace_id,edge_id)
);
CREATE INDEX IF NOT EXISTS idx_chain_addresses_lookup ON chain_addresses(chain,address);
CREATE INDEX IF NOT EXISTS idx_bridge_interactions_case ON bridge_interactions(case_id,timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cross_chain_links_case ON cross_chain_links(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_chain_links_tx ON cross_chain_links(source_transaction_hash,destination_transaction_hash);
CREATE INDEX IF NOT EXISTS idx_cross_chain_trace_case ON cross_chain_trace_runs(case_id,created_at DESC);
CREATE TABLE IF NOT EXISTS cross_chain_pattern_observations (
  pattern_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  trace_id UUID NOT NULL REFERENCES cross_chain_trace_runs(trace_id) ON DELETE CASCADE,
  pattern_type TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence_level TEXT NOT NULL,
  severity TEXT NOT NULL,
  description TEXT NOT NULL,
  explanation TEXT NOT NULL,
  link_ids JSONB NOT NULL DEFAULT '[]',
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  metadata JSONB NOT NULL DEFAULT '{}',
  fingerprint TEXT NOT NULL UNIQUE,
  observed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cross_chain_patterns_case ON cross_chain_pattern_observations(case_id,observed_at DESC);

INSERT INTO chains(chain_id,name,family,native_asset,address_format,explorer_base_url,block_time_seconds,finality_model,provider,historical_capability,realtime_capability,token_transfer_capability,bridge_detection_capability,metadata)
VALUES
('ethereum','Ethereum','EVM','ETH','0x + 40 hex characters','https://etherscan.io',12,'probabilistic','Alchemy Ethereum','NOT_CONFIGURED','NOT_CONFIGURED','NOT_CONFIGURED','SUPPORTED','{}'),
('tron','Tron','TRON','TRX','Base58 T + 33 characters','https://tronscan.org/#/transaction/',3,'delegated-finality','TronGrid','NOT_CONFIGURED','NOT_CONFIGURED','NOT_CONFIGURED','SUPPORTED','{}')
ON CONFLICT(chain_id) DO NOTHING;
