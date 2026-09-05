import pytest
from datetime import datetime
from app.domain import (
    Chain,
    VaspClassification,
    AttributionEvidenceType,
    VaspEntity,
    VaspBlockchainAddress,
    AddressCluster,
    AttributionEvidence,
    TraceResult,
    GraphNode,
    Transfer,
    EntityType,
    DataMode,
    TraceDirection,
)
from app.vasp_attribution_engine import VASPAttributionEngine, THRESHOLD_KNOWN, THRESHOLD_PROBABLE


@pytest.fixture
def sample_vasp_dataset():
    binance = VaspEntity(
        id="vasp-1",
        legal_name="Binance Holdings Ltd",
        trading_name="Binance",
        jurisdiction="Cayman Islands",
        website="https://binance.com",
        regulatory_status="REGISTERED",
        entity_type=EntityType.VASP,
    )
    kraken = VaspEntity(
        id="vasp-2",
        legal_name="Payward Inc",
        trading_name="Kraken",
        jurisdiction="United States",
        website="https://kraken.com",
        regulatory_status="REGISTERED",
        entity_type=EntityType.VASP,
    )

    cluster_1 = AddressCluster(
        id="cl-1",
        chain=Chain.ETHEREUM,
        entity_id="vasp-1",
        cluster_type="HOT_WALLET_CLUSTER",
        confidence=0.95,
        provenance="Cluster analysis",
    )

    addr_binance = VaspBlockchainAddress(
        id="addr-1",
        chain=Chain.ETHEREUM,
        address="0x28c6c06298d514db089934071355e5743bf21d60",
        entity_id="vasp-1",
        address_type="HOT_WALLET",
        cluster_id="cl-1",
        source="CURATED_REGISTRY",
        provenance="Public Exchange Registry",
        confidence=0.98,
    )

    addr_kraken = VaspBlockchainAddress(
        id="addr-2",
        chain=Chain.ETHEREUM,
        address="0x2910543af39aba0cd09bfb2650210b2d86da3536",
        entity_id="vasp-2",
        address_type="DEPOSIT_PROXY",
        source="CURATED_REGISTRY",
        provenance="Exchange Deposit Registry",
        confidence=0.92,
    )

    return [binance, kraken], [addr_binance, addr_kraken], [cluster_1]


def test_direct_known_address_attribution(sample_vasp_dataset):
    entities, addresses, clusters = sample_vasp_dataset
    engine = VASPAttributionEngine(entities, addresses, clusters)

    result = engine.analyze(Chain.ETHEREUM, "0x28c6c06298d514db089934071355e5743bf21d60")

    assert result.candidate_entity is not None
    assert result.candidate_entity.id == "vasp-1"
    assert result.classification == VaspClassification.KNOWN
    assert result.confidence >= THRESHOLD_KNOWN
    assert len(result.supporting_evidence) >= 1
    assert any(ev.evidence_type == AttributionEvidenceType.KNOWN_ADDRESS for ev in result.supporting_evidence)
    assert any(ev.evidence_type == AttributionEvidenceType.KNOWN_CLUSTER for ev in result.supporting_evidence)


def test_unknown_address_attribution(sample_vasp_dataset):
    entities, addresses, clusters = sample_vasp_dataset
    engine = VASPAttributionEngine(entities, addresses, clusters)

    result = engine.analyze(Chain.ETHEREUM, "0x0000000000000000000000000000000000009999")

    assert result.candidate_entity is None
    assert result.classification == VaspClassification.UNKNOWN
    assert result.confidence == 0.0
    assert len(result.supporting_evidence) == 0


def test_multihop_trace_attribution_probable(sample_vasp_dataset):
    entities, addresses, clusters = sample_vasp_dataset
    engine = VASPAttributionEngine(entities, addresses, clusters)

    victim_address = "0xaaaa111122223333444455556666777788889999"
    binance_address = "0x28c6c06298d514db089934071355e5743bf21d60"

    trace = TraceResult(
        trace_id="tr-101",
        case_id="case-101",
        root_address=victim_address,
        mode=DataMode.HISTORICAL,
        provider="Alchemy",
        direction=TraceDirection.FORWARD,
        nodes=[
            GraphNode(id="n1", address=victim_address, chain=Chain.ETHEREUM, depth=0),
            GraphNode(id="n2", address=binance_address, chain=Chain.ETHEREUM, depth=1),
        ],
        edges=[],
        signals=[],
        evidence=[],
    )

    sample_transfer = Transfer(
        tx_hash="0xhash1",
        chain=Chain.ETHEREUM,
        source=victim_address,
        destination=binance_address,
        asset="ETH",
        amount="10.5",
        provider="Alchemy",
        timestamp=datetime.utcnow(),
    )

    result = engine.analyze(Chain.ETHEREUM, victim_address, trace=trace, transfers=[sample_transfer])

    assert result.candidate_entity is not None
    assert result.candidate_entity.id == "vasp-1"
    assert result.classification in [VaspClassification.PROBABLE, VaspClassification.KNOWN]
    assert result.graph_distance == 1
    assert result.fund_amount == 10.5
    assert any(ev.evidence_type == AttributionEvidenceType.TRANSACTION_TO_KNOWN_ENTITY for ev in result.supporting_evidence)


def test_conflicting_evidence_penalty(sample_vasp_dataset):
    entities, addresses, clusters = sample_vasp_dataset

    conflicting_ev = AttributionEvidence(
        id="ev-conflict-1",
        address="0xvictim",
        entity_id="vasp-2",
        evidence_type=AttributionEvidenceType.HISTORICAL_ASSOCIATION,
        evidence_description="Historical association with Kraken",
        source="HistoricalFeed",
        confidence=0.75,
    )

    engine = VASPAttributionEngine(entities, addresses, clusters, evidence_records=[conflicting_ev])

    trace = TraceResult(
        trace_id="tr-102",
        case_id="case-102",
        root_address="0xvictim",
        mode=DataMode.HISTORICAL,
        provider="Alchemy",
        direction=TraceDirection.FORWARD,
        nodes=[
            GraphNode(id="n1", address="0xvictim", chain=Chain.ETHEREUM, depth=0),
            GraphNode(id="n2", address="0x28c6c06298d514db089934071355e5743bf21d60", chain=Chain.ETHEREUM, depth=1),
        ],
        edges=[],
        signals=[],
        evidence=[],
    )

    result = engine.analyze(Chain.ETHEREUM, "0xvictim", trace=trace)

    assert len(result.contradictory_evidence) >= 1
    assert "conflicting signal" in result.explanation
