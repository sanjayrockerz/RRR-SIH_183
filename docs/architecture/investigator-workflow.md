# Investigator workflow

The case workflow is persisted through `case_workflow_events` and the case `workflow_stage` field. Stages include `NEW`, `INTAKE_COMPLETE`, `DATA_ACQUISITION`, `TRACE_ANALYZED`, `PATTERNS_ANALYZED`, `RISK_ASSESSED`, `WATCHING`, `ALERTED`, `REPORT_READY` and `CLOSED`.

`GET /api/v1/cases/{case_id}/workflow` returns stage, timing, provider, result count, error and evidence references. This lets the UI show what actually happened to a case instead of inferring progress from page state.
