from datetime import datetime, timezone
import pytest

from app.domain import Chain, RealtimeEvent, RealtimeProcessingAttempt, RealtimeProcessingStatus
from app.realtime_service import RealtimeService


def event():
    return RealtimeEvent(event_id="event-1", provider="fixture", chain=Chain.ETHEREUM, received_at=datetime.now(timezone.utc), transaction_hash="0x" + "a" * 64, from_address="0x" + "1" * 40, to_address="0x" + "2" * 40, asset="ETH", amount="1")


class Repo:
    def __init__(self, fail=False): self.fail=fail; self.statuses=[]
    async def ingest_realtime_event(self, item): return item, False
    async def list_all_watches(self, chain):
        if self.fail: raise RuntimeError("processing failed")
        return []
    async def record_realtime_attempt(self, event_id, status, error=None):
        self.statuses.append((event_id,status,error))
        return RealtimeProcessingAttempt(attempt_id="attempt",event_id=event_id,attempt_number=len(self.statuses),status=status,started_at=datetime.now(timezone.utc),completed_at=datetime.now(timezone.utc),error=error)
    async def mark_realtime_failure(self,*args): return event()
    async def reset_realtime_event(self,event_id): return event()


@pytest.mark.asyncio
async def test_successful_delivery_is_recorded_as_applied():
    repo=Repo(); service=RealtimeService(repo, provider=object(), pattern_service=object(), risk_service=object())
    await service._process_events([event()])
    assert repo.statuses[0][1] == RealtimeProcessingStatus.APPLIED


@pytest.mark.asyncio
async def test_failed_delivery_is_recorded_and_rethrown_for_operational_retry():
    repo=Repo(fail=True); service=RealtimeService(repo, provider=object(), pattern_service=object(), risk_service=object())
    with pytest.raises(RuntimeError): await service._process_events([event()])
    assert repo.statuses[0][1] == RealtimeProcessingStatus.FAILED

def test_watch_request_accepts_valid_tron_address():
    from app.domain import WatchCreate
    request=WatchCreate(address="T"+"a"*33,chain=Chain.TRON)
    assert request.chain==Chain.TRON

@pytest.mark.asyncio
async def test_simulated_watch_does_not_require_provider_configuration():
    from uuid import uuid4
    from datetime import datetime, timezone
    from app.domain import InvestigationCase, WatchCreate, WatchTarget

    case_id = str(uuid4())
    class SimulatedRepo(Repo):
        async def get(self, requested_case_id):
            now = datetime.now(timezone.utc)
            return InvestigationCase(case_id=requested_case_id, title="Test", fraud_type="Investment fraud", priority="HIGH", status="OPEN", created_at=now, updated_at=now) if requested_case_id == case_id else None
        async def create_watch(self, watch):
            return watch

    class UnconfiguredProvider:
        async def subscribe_to_address_activity(self, *args):
            raise AssertionError("simulated watches must not call the live provider")

    service = RealtimeService(SimulatedRepo(), provider=UnconfiguredProvider(), pattern_service=object(), risk_service=object())
    watch = await service.create_watch(case_id, WatchCreate(address="0x" + "1" * 40, source="SIMULATED"))
    assert isinstance(watch, WatchTarget)
    assert watch.status.value == "ACTIVE"
    assert watch.provider == "SIMULATED EVENT SOURCE"
