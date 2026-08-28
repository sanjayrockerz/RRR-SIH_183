from abc import ABC, abstractmethod
from .attribution import AttributionEngine
from .domain import AddressAttribution, AttributionSource, Chain, Entity, ResolvedAttribution


class EntityIntelligenceProvider(ABC):
    """Provider-independent boundary for source-backed entity intelligence."""

    name = "unknown"

    @abstractmethod
    def resolve(self, chain: Chain, address: str) -> ResolvedAttribution:
        raise NotImplementedError


class CuratedAttributionProvider(EntityIntelligenceProvider):
    """Uses the persisted curated catalog; it makes no commercial-vendor claims."""

    name = "Persisted curated attribution catalog"

    def __init__(self, entities: list[Entity], sources: list[AttributionSource], records: list[AddressAttribution]):
        self._engine = AttributionEngine(entities, sources, records)

    def resolve(self, chain: Chain, address: str) -> ResolvedAttribution:
        return self._engine.resolve(chain, address)
