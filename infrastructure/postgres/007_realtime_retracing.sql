CREATE TABLE IF NOT EXISTS realtime_events (
  event_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_event_id TEXT,
  chain TEXT NOT NULL,
  event_type TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  observed_at TIMESTAMPTZ,
  block_number BIGINT,
  block_hash TEXT,
  transaction_hash TEXT NOT NULL,
  transfer_index INTEGER,
  from_address TEXT NOT NULL,
  to_address TEXT NOT NULL,
  asset TEXT NOT NULL,
  amount TEXT NOT NULL,
  contract_address TEXT,
  token_id TEXT,
  raw_provider_reference JSONB NOT NULL DEFAULT '{}',
  processing_status TEXT NOT NULL,
  confirmation_state TEXT NOT NULL,
  removed BOOLEAN NOT NULL DEFAULT FALSE,
  error TEXT,
  UNIQUE(provider,provider_event_id)
);
CREATE TABLE IF NOT EXISTS watch_targets (
  watch_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  provider TEXT NOT NULL,
  subscription_id TEXT,
  last_event_at TIMESTAMPTZ,
  last_processed_block BIGINT,
  last_processed_event TEXT,
  expansion_policy TEXT NOT NULL,
  max_hops INTEGER NOT NULL,
  max_new_nodes_per_event INTEGER NOT NULL,
  max_new_edges_per_event INTEGER NOT NULL,
  max_value NUMERIC NOT NULL DEFAULT 0,
  allowed_assets JSONB NOT NULL DEFAULT '[]',
  error TEXT,
  UNIQUE(case_id,chain,address)
);
CREATE TABLE IF NOT EXISTS watch_subscriptions (
  subscription_id UUID PRIMARY KEY,
  watch_id UUID NOT NULL REFERENCES watch_targets(watch_id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  provider_subscription_id TEXT,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS realtime_event_applications (
  event_id TEXT NOT NULL REFERENCES realtime_events(event_id) ON DELETE CASCADE,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  watch_id UUID NOT NULL REFERENCES watch_targets(watch_id) ON DELETE CASCADE,
  transaction_id UUID REFERENCES transactions(transaction_id),
  evidence_id UUID REFERENCES evidence(evidence_id),
  applied_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(event_id,case_id)
);
CREATE TABLE IF NOT EXISTS processing_attempts (
  attempt_id UUID PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES realtime_events(event_id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS investigation_timeline (
  event_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  timestamp TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  source TEXT NOT NULL,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS change_sets (
  change_set_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  realtime_event_id TEXT REFERENCES realtime_events(event_id),
  created_at TIMESTAMPTZ NOT NULL,
  before_state JSONB NOT NULL DEFAULT '{}',
  after_state JSONB NOT NULL DEFAULT '{}',
  changes JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS alerts (
  alert_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  subject_id TEXT NOT NULL,
  alert_type TEXT NOT NULL,
  title TEXT NOT NULL,
  explanation TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  risk_delta NUMERIC NOT NULL DEFAULT 0,
  pattern_ids JSONB NOT NULL DEFAULT '[]',
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  fingerprint TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_realtime_events_tx ON realtime_events(chain,transaction_hash);
CREATE INDEX IF NOT EXISTS idx_realtime_events_status ON realtime_events(processing_status,received_at);
CREATE INDEX IF NOT EXISTS idx_watch_targets_case ON watch_targets(case_id,status);
CREATE INDEX IF NOT EXISTS idx_watch_targets_address ON watch_targets(chain,address);
CREATE INDEX IF NOT EXISTS idx_timeline_case ON investigation_timeline(case_id,timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_change_sets_case ON change_sets(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_case ON alerts(case_id,created_at DESC);
