import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from .domain import AuditEvent, InvestigationReport, ReportCreateRequest, ReportType, TimelineEvent


class ReportService:
    """Builds immutable, evidence-backed report snapshots from persisted data."""

    def __init__(self, repository):
        self.repository = repository

    async def generate(self, case_id: str, request: ReportCreateRequest) -> InvestigationReport:
        case = await self.repository.get(case_id)
        if not case:
            raise ValueError("Case not found")
        trace = await self.repository.get_trace(case_id, request.trace_id) if request.trace_id else case.latest_trace
        evidence = await self.repository.list_evidence(case_id)
        patterns = await self.repository.list_patterns(case_id, trace.trace_id) if trace else []
        assessment = await self.repository.latest_risk(case_id) if trace else None
        report = self._build(case, trace, evidence, patterns, assessment, request)
        persisted = await self.repository.persist_report(report)
        await self.repository.append_audit_event(AuditEvent(event_id=str(uuid4()), case_id=case_id, action="REPORT_GENERATED", resource_type="REPORT", resource_id=persisted.report_id, actor_id=request.created_by, occurred_at=persisted.created_at, metadata={"report_type": persisted.report_type.value, "evidence_count": len(persisted.evidence_ids)}))
        await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()), case_id=case_id, timestamp=persisted.created_at, event_type="REPORT_GENERATED", summary="Evidence-backed investigation report snapshot generated.", source="ReportService", evidence_ids=persisted.evidence_ids, metadata={"report_id": persisted.report_id, "report_type": persisted.report_type.value}))
        return persisted

    async def list(self, case_id: str) -> list[InvestigationReport]:
        return await self.repository.list_reports(case_id)

    async def get(self, case_id: str, report_id: str) -> InvestigationReport | None:
        return await self.repository.get_report(case_id, report_id)

    def _build(self, case, trace, evidence, patterns, assessment, request):
        now = datetime.now(timezone.utc)
        evidence_ids = sorted({item.evidence_id for item in evidence})
        pattern_ids = sorted({item.pattern_id for item in patterns})
        lines = [
            "REPORT CLASSIFICATION: INVESTIGATIVE WORK PRODUCT",
            "",
            f"CASE: {case.case_id}",
            f"TITLE: {case.title}",
            f"FRAUD TYPE: {case.fraud_type}",
            f"REPORT TYPE: {request.report_type.value}",
            "",
            "OBSERVED FACTS",
            f"- Reported wallets in the case: {len(case.wallets)}.",
            f"- Persisted blockchain transaction relationships: {len(case.transactions)}.",
        ]
        if trace:
            lines.extend([
                f"- Trace {trace.trace_id} used provider mode {trace.mode} with provider {trace.provider}.",
                f"- Bounded graph contains {trace.metrics.node_count} nodes and {trace.metrics.edge_count} edges.",
                f"- Unique observed transactions: {trace.metrics.unique_transaction_count}.",
                f"- Trace status: {trace.status}.",
            ])
        else:
            lines.append("- No persisted trace was available when this snapshot was generated.")
        lines.extend(["", "BEHAVIORAL OBSERVATIONS"])
        if patterns:
            for item in patterns:
                lines.append(f"- {item.pattern_type.value}: {item.description} Evidence: {', '.join(item.evidence_ids) or 'none recorded'}.")
        else:
            lines.append("- No persisted pattern observations were available; no behavioral conclusion is made.")
        lines.extend(["", "INVESTIGATIVE POSTURE"])
        if assessment:
            lines.append(f"- Persisted rule-based posture: {assessment.band.value} ({assessment.score:.2f}/100), calculated at {assessment.calculated_at.isoformat()}.")
            lines.append("- This posture is an investigative prioritization aid and is not a legal or criminal determination.")
        else:
            lines.append("- No persisted risk assessment was available; no risk score is asserted.")
        lines.extend(["", "EVIDENCE REFERENCES", f"- Evidence records: {', '.join(evidence_ids) or 'none persisted'}", "- Source observations remain in the canonical PostgreSQL evidence ledger.", "", "LIMITATIONS", "- This snapshot contains observed blockchain data and derived analytical observations only.", "- Attribution, risk posture, and pattern observations retain their own provenance and must be reviewed with their supporting evidence.", "- This report is not an authenticated legal filing or an evidence export; production export requires identity, authorization, and retention controls."])
        content = "\n".join(lines)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return InvestigationReport(report_id=str(uuid4()), case_id=case.case_id, report_type=request.report_type, trace_id=trace.trace_id if trace else None, title=f"{request.report_type.value.replace('_', ' ').title()} — {case.title}", content=content, evidence_ids=evidence_ids, pattern_ids=pattern_ids, assessment_id=assessment.assessment_id if assessment else None, content_hash=digest, created_at=now, created_by=request.created_by)
