from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
import httpx

from ..config import settings
from ..domain import Chain, normalize_address
from .schemas import ThreatIntelProviderResult, ThreatIntelStatus


class ThreatIntelProvider(Protocol):
    source: str
    source_version: str

    def configured(self) -> bool: ...

    async def query(self, chain: Chain, address: str) -> list[ThreatIntelProviderResult]: ...


class ThreatIntelProviderError(RuntimeError):
    pass


class ChainabuseProvider:
    source = "Chainabuse"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, source_version: str | None = None):
        self.api_key = api_key if api_key is not None else settings.chainabuse_api_key
        self.base_url = (base_url or settings.chainabuse_base_url).rstrip("/")
        self.source_version = source_version or settings.chainabuse_source_version

    def configured(self) -> bool:
        return bool(self.api_key)

    async def query(self, chain: Chain, address: str) -> list[ThreatIntelProviderResult]:
        if not self.configured():
            return []
        normalized = normalize_address(chain, address)
        params = {"address": normalized, "chain": chain.value, "page": 1, "perPage": 50}
        retrieved_at = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=settings.threat_intel_timeout_seconds) as client:
                response = await client.get(self.base_url + "/reports", params=params, auth=(self.api_key, self.api_key))
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ThreatIntelProviderError("Chainabuse request failed") from exc

        rows = payload if isinstance(payload, list) else payload.get("reports", payload.get("data", [])) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ThreatIntelProviderError("Chainabuse returned an unexpected response")
        if not rows:
            return [ThreatIntelProviderResult(source=self.source, source_version=self.source_version, indicator=normalized, match_type=ThreatIntelStatus.NO_MATCH, confidence=None, reference=None, raw_status=ThreatIntelStatus.NO_MATCH, retrieved_at=retrieved_at)]

        results = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_confidence = row.get("confidence", row.get("confidenceScore"))
            try:
                confidence = float(raw_confidence) if raw_confidence is not None else None
                if confidence is not None and confidence > 1:
                    confidence /= 100
            except (TypeError, ValueError):
                confidence = None
            report_id = row.get("id", row.get("reportId"))
            reference = row.get("url") or (f"https://www.chainabuse.com/report/{report_id}" if report_id else None)
            results.append(ThreatIntelProviderResult(source=self.source, source_version=self.source_version, indicator=str(row.get("indicator") or row.get("address") or normalized), match_type=ThreatIntelStatus.DIRECT_MATCH, confidence=confidence, reference=reference, raw_status=ThreatIntelStatus.DIRECT_MATCH, retrieved_at=retrieved_at))
        return results or [ThreatIntelProviderResult(source=self.source, source_version=self.source_version, indicator=normalized, match_type=ThreatIntelStatus.NO_MATCH, confidence=None, reference=None, raw_status=ThreatIntelStatus.NO_MATCH, retrieved_at=retrieved_at)]


class DevelopmentThreatIntelProvider:
    """Explicit test/development provider; never enabled implicitly in production."""

    source = "DEVELOPMENT_THREAT_INTEL"
    source_version = "development-fixture-v1"

    def __init__(self, records: dict[tuple[Chain, str], ThreatIntelProviderResult] | None = None):
        self.records = records or {}

    def configured(self) -> bool:
        return True

    async def query(self, chain: Chain, address: str) -> list[ThreatIntelProviderResult]:
        result = self.records.get((chain, normalize_address(chain, address)))
        if result:
            return [result]
        return [ThreatIntelProviderResult(source=self.source, source_version=self.source_version, indicator=normalize_address(chain, address), match_type=ThreatIntelStatus.NO_MATCH, confidence=None, reference="fixture://development-threat-intel", raw_status=ThreatIntelStatus.NO_MATCH, retrieved_at=datetime.now(timezone.utc))]
