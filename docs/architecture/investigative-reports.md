# Evidence-backed investigative reports

Reports are immutable snapshots generated from persisted case state. `ReportService` reads the selected case, bounded trace, pattern observations, risk assessment, and evidence references through repository interfaces; it does not query a provider directly or invent missing observations.

Every report stores a content SHA-256 hash plus the IDs of the evidence, patterns, assessment, and trace used to build it. A later report is a new record, so changing evidence or risk posture never rewrites a historical report. The report language separates `OBSERVED FACTS`, `BEHAVIORAL OBSERVATIONS`, `INVESTIGATIVE POSTURE`, `EVIDENCE REFERENCES`, and `LIMITATIONS`.

The current API supports generating and listing case-scoped snapshots and retrieving one by ID. It is not an authenticated export facility: actor identity is an optional client field, and production deployment must add OIDC/RBAC, case authorization, retention, signed export controls, and audit review before reports are treated as official filings.
