ALTER TABLE evidence ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS integrity_status TEXT NOT NULL DEFAULT 'UNVERIFIED';
CREATE INDEX IF NOT EXISTS idx_evidence_content_hash ON evidence(content_hash);

CREATE TABLE IF NOT EXISTS evidence_manifests (
  manifest_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  algorithm TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
  created_at TIMESTAMPTZ NOT NULL,
  created_by TEXT
);
CREATE TABLE IF NOT EXISTS evidence_manifest_items (
  manifest_id UUID NOT NULL REFERENCES evidence_manifests(manifest_id) ON DELETE CASCADE,
  evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
  content_hash TEXT NOT NULL,
  PRIMARY KEY(manifest_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS evidence_chain_events (
  event_id UUID PRIMARY KEY,
  evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  actor_id TEXT,
  occurred_at TIMESTAMPTZ NOT NULL,
  previous_hash TEXT,
  event_hash TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_evidence_manifests_case ON evidence_manifests(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_manifest_items_evidence ON evidence_manifest_items(evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chain_events_evidence ON evidence_chain_events(evidence_id,occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_chain_events_case ON evidence_chain_events(case_id,occurred_at DESC);
