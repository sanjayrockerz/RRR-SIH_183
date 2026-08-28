from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.domain import CaseCreate, Evidence, InvestigationCase, ReportCreateRequest, ReportType
from app.report_service import ReportService


class Repo:
    def __init__(self):
        self.saved = None
        self.audit = []
        self.timeline = []
        self.case = InvestigationCase(case_id="case-1", title="Test case", fraud_type="Phishing", priority="HIGH", status="OPEN", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc), wallets=[], transactions=[])

    async def get(self, case_id): return self.case if case_id == "case-1" else None
    async def get_trace(self, case_id, trace_id): return None
    async def list_evidence(self, case_id): return [Evidence(evidence_id="e-1", case_id=case_id, type="TRANSACTION", chain="ethereum", tx_hash="0x"+"a"*64, source="fixture", captured_at=datetime(2026,1,1,tzinfo=timezone.utc), metadata={})]
    async def list_patterns(self, case_id, trace_id): return []
    async def latest_risk(self, case_id): return None
    async def persist_report(self, report): self.saved = report; return report
    async def append_audit_event(self, event): self.audit.append(event)
    async def append_timeline(self, event): self.timeline.append(event)


@pytest.mark.asyncio
async def test_report_is_evidence_backed_and_hashed():
    repo = Repo()
    result = await ReportService(repo).generate("case-1", ReportCreateRequest(report_type=ReportType.EVIDENCE, created_by="test"))
    assert result.evidence_ids == ["e-1"]
    assert len(result.content_hash) == 64
    assert "OBSERVED FACTS" in result.content
    assert "not an authenticated legal filing" in result.content
    assert repo.audit[0].action == "REPORT_GENERATED"


@pytest.mark.asyncio
async def test_missing_case_is_rejected():
    with pytest.raises(ValueError, match="Case not found"):
        await ReportService(Repo()).generate("missing", ReportCreateRequest())
