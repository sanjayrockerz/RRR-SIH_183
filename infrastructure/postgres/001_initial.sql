CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS cases (
  case_id UUID PRIMARY KEY,
  external_case_id TEXT,
  title TEXT NOT NULL,
  fraud_type TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);

CREATE TABLE IF NOT EXISTS wallets (
  wallet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(chain,address)
);
CREATE TABLE IF NOT EXISTS case_wallets (
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  wallet_id UUID NOT NULL REFERENCES wallets(wallet_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'REPORTED',
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(case_id,wallet_id)
);
CREATE INDEX IF NOT EXISTS idx_case_wallets_case_id ON case_wallets(case_id);
CREATE INDEX IF NOT EXISTS idx_case_wallets_wallet_id ON case_wallets(wallet_id);

CREATE TABLE IF NOT EXISTS transactions (
  transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain TEXT NOT NULL,
  tx_hash TEXT NOT NULL,
  block_number BIGINT,
  timestamp TIMESTAMPTZ,
  status TEXT,
  from_address TEXT NOT NULL DEFAULT '',
  to_address TEXT NOT NULL DEFAULT '',
  native_value NUMERIC,
  fee NUMERIC,
  raw_reference JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(chain,tx_hash)
);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address);
CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_address);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);

CREATE TABLE IF NOT EXISTS case_transactions (
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(case_id,transaction_id)
);

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
  source_wallet TEXT NOT NULL,
  destination_wallet TEXT NOT NULL,
  asset TEXT NOT NULL,
  amount TEXT NOT NULL,
  timestamp TIMESTAMPTZ,
  hop INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(case_id,transaction_id,source_wallet,destination_wallet,hop)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_case_id ON graph_edges(case_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_transaction_id ON graph_edges(transaction_id);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  evidence_type TEXT NOT NULL,
  chain TEXT NOT NULL,
  tx_hash TEXT,
  source TEXT NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  content_hash TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(case_id,chain,tx_hash,evidence_type)
);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_tx_hash ON evidence(tx_hash);
