CREATE TABLE IF NOT EXISTS vasp_action_packages (
  package_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  report_id UUID NOT NULL REFERENCES investigation_reports(report_id) ON DELETE RESTRICT,
  package_version TEXT NOT NULL,
  payload JSONB NOT NULL,
  integrity_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  created_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_vasp_action_packages_case ON vasp_action_packages(case_id, created_at DESC);
ALTER TABLE investigation_reports ADD COLUMN IF NOT EXISTS version TEXT NOT NULL DEFAULT '1.0';
ALTER TABLE investigation_reports ADD COLUMN IF NOT EXISTS manifest_id UUID;
ALTER TABLE investigation_reports ADD COLUMN IF NOT EXISTS manifest_hash TEXT;
ALTER TABLE investigation_reports ADD COLUMN IF NOT EXISTS sections JSONB NOT NULL DEFAULT '{}';
