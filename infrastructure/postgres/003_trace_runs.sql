CREATE TABLE IF NOT EXISTS trace_runs (
  trace_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  root_wallet TEXT NOT NULL,
  chain TEXT NOT NULL,
  direction TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  limits JSONB NOT NULL DEFAULT '{}',
  node_count INTEGER NOT NULL DEFAULT 0,
  edge_count INTEGER NOT NULL DEFAULT 0,
  transaction_count INTEGER NOT NULL DEFAULT 0,
  provider TEXT NOT NULL,
  mode TEXT NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_trace_runs_case ON trace_runs(case_id,completed_at DESC);
ALTER TABLE graph_edges ADD COLUMN IF NOT EXISTS trace_id UUID REFERENCES trace_runs(trace_id) ON DELETE CASCADE;
ALTER TABLE graph_edges DROP CONSTRAINT IF EXISTS graph_edges_case_id_transaction_id_source_wallet_destination_wallet_hop_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_trace_identity ON graph_edges(trace_id,transaction_id,source_wallet,destination_wallet,hop) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_graph_edges_trace_id ON graph_edges(trace_id);
