from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..domain import Chain, normalize_address
from .provider import ThreatIntelProvider, ThreatIntelProviderError
from .schemas import ThreatIntelObservation, ThreatIntelResponse, ThreatIntelStatus


class ThreatIntelService:
    def __init__(self, repository, providers: list[ThreatIntelProvider] | None = None):
        self.repository = repository
        self.providers = providers if providers is not None else []

    async def persisted_wallet(self, chain: Chain, address: str) -> ThreatIntelResponse:
        normalized = normalize_address(chain, address)
        observations = await self.repository.threat_intel_observations(chain=chain, address=normalized)
        status = "DIRECT_MATCH" if any(item.match_type == ThreatIntelStatus.DIRECT_MATCH for item in observations) else (observations[0].raw_status.value if observations else "NO_DATA")
        return ThreatIntelResponse(status=status, chain=chain, address=normalized, observations=observations, generated_at=datetime.now(timezone.utc))

    async def persisted_case(self, case_id: str) -> ThreatIntelResponse:
        observations = await self.repository.threat_intel_observations(case_id=case_id)
        status = "DIRECT_MATCH" if any(item.match_type == ThreatIntelStatus.DIRECT_MATCH for item in observations) else (observations[0].raw_status.value if observations else "NO_DATA")
        return ThreatIntelResponse(status=status, observations=observations, generated_at=datetime.now(timezone.utc))

    async def refresh(self, case_id: str, wallets: list[tuple[Chain, str]]) -> ThreatIntelResponse:
        all_observations: list[ThreatIntelObservation] = []
        configured = [provider for provider in self.providers if provider.configured()]
        for chain, address in wallets:
            normalized = normalize_address(chain, address)
            if not configured:
                now = datetime.now(timezone.utc)
                result = ThreatIntelObservation(observation_id=str(uuid4()), chain=chain, address=normalized, source="THREAT_INTEL", source_version="provider-boundary-v1", indicator=normalized, match_type=ThreatIntelStatus.NOT_CONFIGURED, confidence=None, reference=None, retrieved_at=now, raw_status=ThreatIntelStatus.NOT_CONFIGURED, case_id=case_id, created_at=now)
                await self.repository.persist_threat_intel(result)
                all_observations.append(result)
                continue
            for provider in configured:
                try:
                    results = await provider.query(chain, normalized)
                except ThreatIntelProviderError:
                    now = datetime.now(timezone.utc)
                    results = [provider_result_error(provider, normalized, now)]
                for result in results:
                    observation = ThreatIntelObservation(observation_id=str(uuid4()), chain=chain, address=normalized, source=result.source, source_version=result.source_version, indicator=result.indicator, match_type=result.match_type, confidence=result.confidence, reference=result.reference, retrieved_at=result.retrieved_at, raw_status=result.raw_status, case_id=case_id, created_at=datetime.now(timezone.utc))
                    await self.repository.persist_threat_intel(observation)
                    all_observations.append(observation)
        status = "DIRECT_MATCH" if any(item.match_type == ThreatIntelStatus.DIRECT_MATCH for item in all_observations) else (all_observations[0].raw_status.value if all_observations else "NO_DATA")
        return ThreatIntelResponse(status=status, observations=all_observations, generated_at=datetime.now(timezone.utc))


def provider_result_error(provider: ThreatIntelProvider, address: str, now: datetime):
    from .schemas import ThreatIntelProviderResult
    return ThreatIntelProviderResult(source=provider.source, source_version=provider.source_version, indicator=address, match_type=ThreatIntelStatus.ERROR, confidence=None, reference=None, raw_status=ThreatIntelStatus.ERROR, retrieved_at=now)
