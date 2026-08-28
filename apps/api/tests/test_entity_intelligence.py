from app.domain import AddressAttribution, AttributionSource, Chain, ConfidenceLevel, Entity, EntityType
from app.entity_intelligence import CuratedAttributionProvider, EntityIntelligenceProvider


def test_curated_provider_preserves_source_backed_resolution():
    entity = Entity(entity_id="entity-1", name="Fixture Exchange", entity_type=EntityType.EXCHANGE)
    source = AttributionSource(source_id="source-1", name="Fixture dataset", source_type="CURATED", reference="fixture://v1", dataset_version="2026-08-26")
    record = AddressAttribution(attribution_id="record-1", chain=Chain.ETHEREUM, address="0x" + "a" * 40, entity_id="entity-1", role="DEPOSIT", confidence=ConfidenceLevel.HIGH, source_id="source-1", source_reference="fixture://v1")
    result = CuratedAttributionProvider([entity], [source], [record]).resolve(Chain.ETHEREUM, record.address)
    assert result.candidates[0].entity.name == "Fixture Exchange"
    assert result.candidates[0].supporting_sources[0].reference == "fixture://v1"


def test_commercial_provider_is_only_an_extension_boundary():
    assert EntityIntelligenceProvider.__abstractmethods__ == {"resolve"}
