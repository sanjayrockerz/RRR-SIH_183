"""Explicit, deterministic attribution data for the development synthetic lab.

This registry is intentionally separate from live intelligence. Its addresses are
reserved demo values and are only merged into attribution resolution for the
development fixture/synthetic workflow.
"""

from datetime import datetime, timezone
from .domain import AddressAttribution, AttributionRole, AttributionSource, Chain, ConfidenceLevel, Entity, EntityType

DEMO_VASP_ADDRESS = "0x9999999999999999999999999999999999999999"
DEMO_ENTITY_ID = "10000000-0000-0000-0000-000000000002"
DEMO_SOURCE_ID = "10000000-0000-0000-0000-000000000001"
DEMO_ATTRIBUTION_ID = "10000000-0000-0000-0000-000000000003"
_FIRST_OBSERVED = datetime(2026, 1, 1, tzinfo=timezone.utc)
_LAST_OBSERVED = datetime(2026, 12, 31, tzinfo=timezone.utc)


def registry() -> tuple[list[Entity], list[AttributionSource], list[AddressAttribution]]:
    return (
        [Entity(
            entity_id=DEMO_ENTITY_ID,
            name="Demo Exchange",
            entity_type=EntityType.VASP,
            legal_name="Demo Exchange (Development Only)",
            jurisdiction="DEVELOPMENT",
            website="https://example.invalid/demo-exchange",
            metadata={"intelligence_mode": "CURATED_INTELLIGENCE", "development_only": True},
        )],
        [AttributionSource(
            source_id=DEMO_SOURCE_ID,
            name="RRR Development Synthetic Attribution Registry",
            source_type="CURATED_DATASET",
            publisher="RRR Development",
            reference="synthetic://vasp-registry/2026-08",
            reliability_level=ConfidenceLevel.HIGH,
            description="Deterministic demo-only attribution. Never represents live blockchain intelligence.",
            dataset_version="2026-08-development",
        )],
        [AddressAttribution(
            attribution_id=DEMO_ATTRIBUTION_ID,
            chain=Chain.ETHEREUM,
            address=DEMO_VASP_ADDRESS,
            entity_id=DEMO_ENTITY_ID,
            role=AttributionRole.DEPOSIT_ADDRESS,
            confidence=ConfidenceLevel.HIGH,
            source_id=DEMO_SOURCE_ID,
            source_reference="synthetic://vasp-registry/2026-08",
            first_seen=_FIRST_OBSERVED,
            last_verified=_LAST_OBSERVED,
            metadata={
                "mode": "DEVELOPMENT_SYNTHETIC",
                "first_observed": _FIRST_OBSERVED.isoformat(),
                "last_observed": _LAST_OBSERVED.isoformat(),
                "evidence": "Deterministic synthetic scenario terminal address",
            },
        )],
    )


def merge(entities, sources, records):
    demo_entities, demo_sources, demo_records = registry()
    entities = list(entities)
    sources = list(sources)
    records = list(records)
    known_entities = {item.entity_id for item in entities}
    known_sources = {item.source_id for item in sources}
    known_records = {(item.chain, item.address.lower(), item.entity_id, item.role, item.source_id) for item in records}
    entities.extend(item for item in demo_entities if item.entity_id not in known_entities)
    sources.extend(item for item in demo_sources if item.source_id not in known_sources)
    records.extend(item for item in demo_records if (item.chain, item.address.lower(), item.entity_id, item.role, item.source_id) not in known_records)
    return entities, sources, records


def is_synthetic_trace(trace) -> bool:
    if not trace:
        return False
    if str(trace.provider).upper() == "DEVELOPMENT SYNTHETIC":
        return True
    return any(
        str(edge.transfer.provider).upper() == "DEVELOPMENT SYNTHETIC"
        or str((edge.transfer.raw_reference or {}).get("source_mode", "")).upper() == "DEVELOPMENT_SYNTHETIC"
        for edge in trace.edges
    )
