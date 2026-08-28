CREATE TABLE IF NOT EXISTS investigation_reports (
  report_id UUID PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  report_type TEXT NOT NULL CHECK (report_type IN ('INVESTIGATION_SUMMARY','FUND_FLOW','EVIDENCE')),
  trace_id UUID REFERENCES trace_runs(trace_id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  evidence_ids JSONB NOT NULL DEFAULT '[]',
  pattern_ids JSONB NOT NULL DEFAULT '[]',
  assessment_id UUID REFERENCES risk_assessments(assessment_id) ON DELETE RESTRICT,
  content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  created_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_investigation_reports_case ON investigation_reports(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_investigation_reports_trace ON investigation_reports(trace_id);
CREATE INDEX IF NOT EXISTS idx_investigation_reports_hash ON investigation_reports(content_hash);
