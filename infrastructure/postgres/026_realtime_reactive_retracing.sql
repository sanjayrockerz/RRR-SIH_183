ALTER TABLE watch_targets ADD COLUMN IF NOT EXISTS last_retrace_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS webhook_deliveries (
  delivery_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  event_id TEXT,
  received_at TIMESTAMPTZ NOT NULL,
  processing_status TEXT NOT NULL,
  raw_reference JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_provider_event ON webhook_deliveries(provider,event_id);

ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS trigger_event_id TEXT;
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_transactions JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_wallets JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_edges JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_patterns JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS risk_before JSONB NOT NULL DEFAULT '{}';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS risk_after JSONB NOT NULL DEFAULT '{}';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS risk_delta NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS vasp_before JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS vasp_after JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_related_cases JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS new_recommendations JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS alerts_generated JSONB NOT NULL DEFAULT '[]';
ALTER TABLE change_sets ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;
