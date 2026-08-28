ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS reviewed_by TEXT;
UPDATE alerts SET updated_at=created_at WHERE updated_at IS NULL;
ALTER TABLE alerts ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS alert_reviews (
  review_id UUID PRIMARY KEY,
  alert_id UUID NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  action TEXT NOT NULL,
  note TEXT,
  actor_id TEXT,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_reviews_alert ON alert_reviews(alert_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_reviews_case ON alert_reviews(case_id,created_at DESC);
