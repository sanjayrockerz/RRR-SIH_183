from datetime import datetime, timezone
from uuid import uuid4

from .domain import AlertReview, AlertReviewRequest, AuditEvent, TimelineEvent


class AlertService:
    """Application boundary for investigator review of generated alerts."""

    def __init__(self, repository):
        self.repository = repository

    async def review(self, case_id: str, alert_id: str, request: AlertReviewRequest):
        alert = await self.repository.get_alert(case_id, alert_id)
        if not alert:
            raise ValueError("Alert not found")
        result = await self.repository.review_alert(case_id, alert_id, request)
        await self.repository.append_audit_event(AuditEvent(event_id=str(uuid4()), case_id=case_id, action=f"ALERT_{request.action.value}", resource_type="ALERT", resource_id=alert_id, actor_id=request.actor_id, occurred_at=datetime.now(timezone.utc), metadata={"from_status": alert.status, "to_status": result.status, "note_present": bool(request.note)}))
        await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()), case_id=case_id, timestamp=datetime.now(timezone.utc), event_type="ALERT_REVIEWED", summary=f"Alert review recorded as {result.status}; this is an investigator workflow action, not a criminality determination.", source="Investigator", evidence_ids=result.evidence_ids, metadata={"alert_id": alert_id, "action": request.action.value, "actor_id_present": bool(request.actor_id)}))
        return result

    async def history(self, case_id: str, alert_id: str) -> list[AlertReview]:
        return await self.repository.alert_reviews(case_id, alert_id)
