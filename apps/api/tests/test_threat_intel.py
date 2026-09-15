from datetime import datetime, timezone

import pytest

from app.domain import Chain
from app.threat_intel.provider import DevelopmentThreatIntelProvider, ThreatIntelProviderError
from app.threat_intel.schemas import ThreatIntelProviderResult, ThreatIntelStatus
from app.threat_intel.service import ThreatIntelService


class Repo:
    def __init__(self):
        self.items = []

    async def persist_threat_intel(self, item):
        self.items.append(item)
        return item

    async def threat_intel_observations(self, **kwargs):
        return [item for item in self.items if kwargs.get("case_id") is None or item.case_id == kwargs["case_id"]]


@pytest.mark.asyncio
async def test_development_provider_preserves_chain_identity_and_no_match():
    repo = Repo()
    service = ThreatIntelService(repo, [DevelopmentThreatIntelProvider()])
    result = await service.refresh("case-1", [(Chain.ETHEREUM, "0x" + "A" * 40)])
    assert result.status == "NO_MATCH"
    assert repo.items[0].address == "0x" + "a" * 40
    assert repo.items[0].raw_status == ThreatIntelStatus.NO_MATCH


@pytest.mark.asyncio
async def test_no_provider_is_not_configured_not_clearance():
    repo = Repo()
    result = await ThreatIntelService(repo, []).refresh("case-1", [(Chain.TRON, "T" + "1" * 33)])
    assert result.status == "NOT_CONFIGURED"
    assert result.observations[0].match_type == ThreatIntelStatus.NOT_CONFIGURED


@pytest.mark.asyncio
async def test_provider_error_is_persisted_as_error():
    class Broken:
        source = "BROKEN"
        source_version = "v1"
        def configured(self): return True
        async def query(self, chain, address): raise ThreatIntelProviderError("offline")

    repo = Repo()
    result = await ThreatIntelService(repo, [Broken()]).refresh("case-1", [(Chain.ETHEREUM, "0x" + "b" * 40)])
    assert result.status == "ERROR"
    assert repo.items[0].source == "BROKEN"
    assert repo.items[0].raw_status == ThreatIntelStatus.ERROR


@pytest.mark.asyncio
async def test_direct_match_preserves_provenance():
    now = datetime.now(timezone.utc)
    match = ThreatIntelProviderResult(source="Chainabuse", source_version="v1", indicator="0x" + "c" * 40, match_type=ThreatIntelStatus.DIRECT_MATCH, confidence=.91, reference="https://example.test/report/1", raw_status=ThreatIntelStatus.DIRECT_MATCH, retrieved_at=now)
    repo = Repo()
    result = await ThreatIntelService(repo, [DevelopmentThreatIntelProvider({(Chain.ETHEREUM, "0x" + "c" * 40): match})]).refresh("case-1", [(Chain.ETHEREUM, "0x" + "C" * 40)])
    assert result.status == "DIRECT_MATCH"
    assert result.observations[0].confidence == .91
    assert result.observations[0].reference.endswith("/1")
