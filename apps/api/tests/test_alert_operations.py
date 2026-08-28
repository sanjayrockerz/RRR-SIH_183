from datetime import datetime, timezone
import pytest

from app.alert_service import AlertService
from app.domain import Alert, AlertReviewRequest, AlertStatus, AlertReviewAction, RiskBand


class Repo:
    def __init__(self):
        self.alert=Alert(alert_id="alert-1",case_id="case-1",subject_id="0x"+"a"*40,alert_type="PATTERN",title="NEW INVESTIGATIVE SIGNAL",explanation="Observed evidence requires review.",severity=RiskBand.HIGH,created_at=datetime.now(timezone.utc))
        self.events=[]
    async def get_alert(self,case_id,alert_id): return self.alert if case_id==self.alert.case_id and alert_id==self.alert.alert_id else None
    async def review_alert(self,case_id,alert_id,request):
        target={AlertReviewAction.ACKNOWLEDGE:AlertStatus.ACKNOWLEDGED,AlertReviewAction.DISMISS:AlertStatus.DISMISSED,AlertReviewAction.ESCALATE:AlertStatus.ESCALATED}[request.action]
        self.alert=self.alert.model_copy(update={"status":target})
        return self.alert
    async def append_audit_event(self,event): self.events.append(event)
    async def append_timeline(self,event): self.events.append(event)
    async def alert_reviews(self,case_id,alert_id): return []


@pytest.mark.asyncio
async def test_review_changes_alert_and_creates_audit_trail():
    repo=Repo(); result=await AlertService(repo).review("case-1","alert-1",AlertReviewRequest(action=AlertReviewAction.ACKNOWLEDGE,actor_id="investigator-1",note="Reviewed linked evidence."))
    assert result.status == AlertStatus.ACKNOWLEDGED
    assert [item.action for item in repo.events if hasattr(item,"action")] == ["ALERT_ACKNOWLEDGE"]
    assert any(getattr(item,"event_type",None)=="ALERT_REVIEWED" for item in repo.events)


@pytest.mark.asyncio
async def test_missing_alert_is_rejected():
    with pytest.raises(ValueError, match="Alert not found"):
        await AlertService(Repo()).review("case-1","missing",AlertReviewRequest(action=AlertReviewAction.DISMISS))
