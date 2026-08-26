from datetime import datetime, timedelta, timezone

from app.domain import (
    AddressAttribution, AttributionRole, Chain, ConfidenceLevel, DataMode, Entity,
    EntityType, GraphEdge, GraphNode, NearestEntityResult, PatternDetectionConfig,
    TraceResult, Transfer, TransactionPath,
)
from app.pattern_engine import PatternEngine

ROOT = "0x" + "a" * 40


def edge(number, source, target, amount="10", seconds=0, asset="ETH", evidence=True):
    transfer = Transfer(
        tx_hash="0x" + number * 64, chain=Chain.ETHEREUM, source=source, destination=target,
        asset=asset, amount=amount, provider="fixture",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds),
    )
    return GraphEdge(edge_id=f"edge-{number}", source=source, target=target, transfer=transfer,
                     hop=1, transaction_hash=transfer.tx_hash, evidence_id=f"ev-{number}" if evidence else None)


def trace(edges):
    nodes = {}
    for item in edges:
        for address in (item.source, item.target):
            nodes.setdefault(address, GraphNode(id=address, address=address))
    paths = [TransactionPath(path_id="path", node_ids=[edges[0].source] + [e.target for e in edges], edges=edges)] if edges else []
    return TraceResult(case_id="case", trace_id="trace", root_address=ROOT, mode=DataMode.HISTORICAL,
                       provider="fixture", nodes=list(nodes.values()), edges=edges, signals=[], evidence=[], paths=paths)


def test_rapid_hop_is_explainable_and_deduplicated():
    a, b, c, d, e = ["0x" + letter * 40 for letter in "abcde"]
    result = PatternEngine(PatternDetectionConfig(rapid_hop_minimum_hops=3)).analyze(
        trace([edge("1", a, b, seconds=0), edge("2", b, c, seconds=120), edge("3", c, d, seconds=240), edge("4", d, e, seconds=360)])
    )
    rapid = [item for item in result if item.pattern_type == "RAPID_HOP"]
    assert len(rapid) == 2  # overlapping, evidence-distinct paths remain visible
    assert all(item.status == "OBSERVED" for item in rapid)
    assert all(len(item.transaction_hashes) == 3 for item in rapid)
    assert all("configured" in item.explanation and item.fingerprint for item in rapid)
    repeated = PatternEngine(PatternDetectionConfig(rapid_hop_minimum_hops=3)).analyze(
        trace([edge("1", a, b, seconds=0), edge("2", b, c, seconds=120), edge("3", c, d, seconds=240), edge("4", d, e, seconds=360)])
    )
    assert {item.fingerprint for item in rapid} == {item.fingerprint for item in repeated if item.pattern_type == "RAPID_HOP"}


def test_fan_out_and_fan_in_are_asset_aware():
    a, b, c, d = ["0x" + letter * 40 for letter in "abcd"]
    fan_out = PatternEngine(PatternDetectionConfig(fan_out_minimum_destinations=3)).analyze(
        trace([edge("1", a, b), edge("2", a, c), edge("3", a, d)])
    )
    assert any(item.pattern_type == "FAN_OUT" for item in fan_out)
    fan_in = PatternEngine(PatternDetectionConfig(fan_in_minimum_sources=3)).analyze(
        trace([edge("4", b, a), edge("5", c, a), edge("6", d, a, asset="USDT")])
    )
    assert any(item.pattern_type == "FAN_IN" for item in fan_in)


def test_peel_chain_and_burst_respect_configuration():
    a, b, c, d = ["0x" + letter * 40 for letter in "abcd"]
    result = PatternEngine(PatternDetectionConfig(
        peel_chain_minimum_hops=2, peel_chain_minimum_retention_ratio=0.05,
        peel_chain_maximum_retention_ratio=0.2, burst_minimum_transactions=3,
    )).analyze(trace([edge("1", a, b, "10", 0), edge("2", b, c, "9", 30), edge("3", c, d, "8", 60)]))
    assert any(item.pattern_type == "PEEL_CHAIN" for item in result)
    assert any(item.pattern_type == "BURST_ACTIVITY" for item in result)


def test_entity_exposure_and_mixer_interaction_use_phase_four_attribution():
    a, b = ["0x" + letter * 40 for letter in "ab"]
    observed = edge("1", a, b)
    entity = Entity(entity_id="mixer", name="Fixture Mixer", entity_type=EntityType.MIXER)
    item = NearestEntityResult(
        entity=entity, address=b, chain=Chain.ETHEREUM, hop_distance=1,
        path=TransactionPath(path_id="path", node_ids=[a, b], edges=[observed]),
        confidence=ConfidenceLevel.HIGH, role=AttributionRole.CONTRACT,
        supporting_attributions=[AddressAttribution(
            attribution_id="attr", chain=Chain.ETHEREUM, address=b, entity_id="mixer",
            role=AttributionRole.CONTRACT, confidence=ConfidenceLevel.HIGH,
            source_id="fixture", source_reference="fixture://mixer")],
        supporting_sources=[], evidence=[], explanation="fixture",
    )
    result = PatternEngine().analyze(trace([observed]), [item])
    assert any(item.pattern_type == "ENTITY_EXPOSURE" for item in result)
    assert any(item.pattern_type == "MIXER_INTERACTION" for item in result)
