from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import uuid4

from .domain import (
    AddressScreeningResult, Chain, IntelligenceConfidence, IntelligenceSourceStatus,
    SanctionsRecord, ScreeningMatch, ScreeningOutcome,
)


class CyberIntelligenceProvider(ABC):
    """Boundary for configured threat/sanctions vendors or approved datasets."""

    name = "unknown"

    @property
    @abstractmethod
    def status(self) -> IntelligenceSourceStatus:
        raise NotImplementedError

    @abstractmethod
    async def screen_address(self, chain: Chain, address: str) -> AddressScreeningResult:
        raise NotImplementedError


class CuratedSanctionsProvider(CyberIntelligenceProvider):
    """Exact-match screening over explicitly supplied, versioned records.

    It intentionally does not infer indirect exposure or treat symbol/name
    similarity as a match.
    """

    name = "Persisted curated sanctions dataset"

    def __init__(self, records: list[SanctionsRecord], configured: bool = True):
        self.records = records
        self.configured = configured

    @property
    def status(self) -> IntelligenceSourceStatus:
        return IntelligenceSourceStatus.CONFIGURED if self.configured else IntelligenceSourceStatus.NOT_CONFIGURED

    async def screen_address(self, chain: Chain, address: str) -> AddressScreeningResult:
        now = datetime.now(timezone.utc)
        normalized = address.lower()
        if not self.configured:
            return AddressScreeningResult(chain=chain, address=normalized, outcome=ScreeningOutcome.NOT_CONFIGURED, source_status=self.status, screened_at=now, explanation="Sanctions screening source is not configured.", limitation="No sanctions conclusion can be drawn until an approved, versioned source is configured.")
        if not self.records:
            return AddressScreeningResult(chain=chain, address=normalized, outcome=ScreeningOutcome.UNKNOWN, source_status=self.status, screened_at=now, explanation="No versioned sanctions records are available.", limitation="No sanctions conclusion can be drawn until database contains valid versioned sanctions records.")
        matches = []
        for record in self.records:
            if record.subject_type.value != "WALLET" or record.normalized_value.lower() != normalized:
                continue
            if record.chain is not None and record.chain != chain:
                continue
            matches.append(ScreeningMatch(match_id=str(uuid4()), record_id=record.record_id, source_id=record.source_id, matched_value=record.value, confidence=record.confidence, explanation="Exact address match in a configured, versioned sanctions record.", evidence_ids=list(record.metadata.get("evidence_ids", []))))
        if matches:
            return AddressScreeningResult(chain=chain, address=normalized, outcome=ScreeningOutcome.DIRECT_MATCH, source_status=self.status, screened_at=now, matches=matches, explanation="The address exactly matched one or more configured source records. This is a source result requiring investigator review, not a legal determination.")
        return AddressScreeningResult(chain=chain, address=normalized, outcome=ScreeningOutcome.NO_MATCH, source_status=self.status, screened_at=now, explanation="No exact address match was found in the configured source records.", limitation="No-match does not establish that an address is safe or free of indirect exposure.")
