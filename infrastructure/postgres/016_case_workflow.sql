ALTER TABLE cases ADD COLUMN IF NOT EXISTS workflow_stage TEXT NOT NULL DEFAULT 'NEW';
CREATE TABLE IF NOT EXISTS case_workflow_events (
  event_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  stage TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  provider TEXT,
  result_count INTEGER,
  error TEXT,
  evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_case_workflow_events_case ON case_workflow_events(case_id,started_at DESC);
