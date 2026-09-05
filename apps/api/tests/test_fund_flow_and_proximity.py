from datetime import datetime, timezone, timedelta
import pytest
from app.domain import (
    AddressCluster,
    AttributionEvidence,
    AttributionEvidenceType,
    AttributionResult,
    Chain,
    GraphEdge,
    GraphNode,
    TraceResult,
    Transfer,
    VaspBlockchainAddress,
    VaspClassification,
    VaspEntity,
)
from app.fund_flow_engine import FundFlowEngine, normalize_to_usd
from app.vasp_proximity_engine import VASPProximityEngine, format_duration_seconds


@pytest.fixture
def sample_vasp_entities():
    return [
        VaspEntity(id="vasp-binance", legal_name="Binance Ltd", trading_name="Binance Global", jurisdiction="Cayman Islands", website="https://binance.com"),
        VaspEntity(id="vasp-kraken", legal_name="Payward Inc.", trading_name="Kraken Exchange", jurisdiction="United States", website="https://kraken.com"),
        VaspEntity(id="vasp-okx", legal_name="Aux Cayes FinTech", trading_name="OKX Exchange", jurisdiction="Seychelles", website="https://okx.com"),
    ]


@pytest.fixture
def sample_vasp_addresses():
    return [
        VaspBlockchainAddress(id="a1", chain=Chain.ETHEREUM, address="0x28c6c06298d514db089934071355e5743bf21d60", entity_id="vasp-binance", address_type="HOT_WALLET"),
        VaspBlockchainAddress(id="a2", chain=Chain.ETHEREUM, address="0x2910543af39aba0cd09bfb2650210b2d86da3536", entity_id="vasp-kraken", address_type="DEPOSIT_PROXY"),
    ]


@pytest.fixture
def sample_attributions(sample_vasp_entities):
    binance = sample_vasp_entities[0]
    kraken = sample_vasp_entities[1]
    return {
        "0x28c6c06298d514db089934071355e5743bf21d60": AttributionResult(
            candidate_entity=binance, classification=VaspClassification.KNOWN, confidence=0.98, explanation="Binance Hot Wallet"
        ),
        "0x2910543af39aba0cd09bfb2650210b2d86da3536": AttributionResult(
            candidate_entity=kraken, classification=VaspClassification.PROBABLE, confidence=0.85, explanation="Kraken Deposit Proxy"
        ),
    }


def test_asset_aware_conversion():
    eth_usd = normalize_to_usd("2.0", "ETH")
    assert eth_usd == 6400.0  # 2.0 * 3200

    usdt_usd = normalize_to_usd("5000", "USDT")
    assert usdt_usd == 5000.0


def test_fund_flow_engine_no_double_counting(sample_attributions):
    now = datetime.now(timezone.utc)
    victim_root = "0xvictim000000000000000000000000000000001"

    # Converging graph topology:
    # Victim -> Intermediary A -> Binance (1.0 ETH)
    # Victim -> Intermediary B -> Binance (1.0 ETH) (converges on same Binance wallet)
    nodes = [
        GraphNode(id="n0", address=victim_root, node_type="WALLET"),
        GraphNode(id="n1", address="0xinterA", node_type="WALLET"),
        GraphNode(id="n2", address="0xinterB", node_type="WALLET"),
        GraphNode(id="n3", address="0x28c6c06298d514db089934071355e5743bf21d60", node_type="VASP"),
    ]
    edges = [
        GraphEdge(source=victim_root, target="0xinterA", transfer=Transfer(chain=Chain.ETHEREUM, source=victim_root, destination="0xinterA", asset="ETH", amount="2.0", tx_hash="0xtx1", provider="TEST_FIXTURE"), asset="ETH", amount="2.0", hop=1, timestamp=now),
        GraphEdge(source="0xinterA", target="0x28c6c06298d514db089934071355e5743bf21d60", transfer=Transfer(chain=Chain.ETHEREUM, source="0xinterA", destination="0x28c6c06298d514db089934071355e5743bf21d60", asset="ETH", amount="1.0", tx_hash="0xtx2", provider="TEST_FIXTURE"), asset="ETH", amount="1.0", hop=2, timestamp=now + timedelta(minutes=5)),
        GraphEdge(source="0xinterA", target="0xinterB", transfer=Transfer(chain=Chain.ETHEREUM, source="0xinterA", destination="0xinterB", asset="ETH", amount="1.0", tx_hash="0xtx3", provider="TEST_FIXTURE"), asset="ETH", amount="1.0", hop=2, timestamp=now + timedelta(minutes=6)),
        GraphEdge(source="0xinterB", target="0x28c6c06298d514db089934071355e5743bf21d60", transfer=Transfer(chain=Chain.ETHEREUM, source="0xinterB", destination="0x28c6c06298d514db089934071355e5743bf21d60", asset="ETH", amount="1.0", tx_hash="0xtx4", provider="TEST_FIXTURE"), asset="ETH", amount="1.0", hop=3, timestamp=now + timedelta(minutes=10)),
    ]

    trace = TraceResult(
        case_id="case-test-flow",
        root_address=victim_root,
        mode="DEVELOPMENT_FIXTURE",
        provider="DevelopmentFixture",
        nodes=nodes,
        edges=edges,
        signals=[],
        evidence=[],
    )

    node_attr_dict = {
        "0x28c6c06298d514db089934071355e5743bf21d60": {
            "classification": VaspClassification.KNOWN,
            "entity_id": "vasp-binance",
            "entity_name": "Binance Ltd",
            "node_type": "VASP",
        }
    }

    engine = FundFlowEngine(trace, node_attr_dict)
    summary = engine.analyze()

    assert summary.case_id == "case-test-flow"
    assert summary.total_victim_loss_usd == 6400.0  # 2.0 ETH * 3200
    # Binance endpoint destination count deduplicated on 0x28c6...
    assert summary.vasp_linked_amount_usd == 3200.0  # 1.0 ETH (deduplicated)
    assert len(summary.propagated_hops) == 4


def test_vasp_proximity_engine_ranking(sample_attributions):
    now = datetime.now(timezone.utc)
    victim_root = "0xvictim000000000000000000000000000000001"

    # Candidate 1: Binance - 2 hops, 1.5 ETH ($4800), high confidence (0.98)
    # Candidate 2: Kraken - 1 hop, 0.2 ETH ($640), lower confidence (0.85)
    nodes = [
        GraphNode(id="n0", address=victim_root, node_type="WALLET"),
        GraphNode(id="n1", address="0xinter", node_type="WALLET"),
        GraphNode(id="n2", address="0x28c6c06298d514db089934071355e5743bf21d60", node_type="VASP"),
        GraphNode(id="n3", address="0x2910543af39aba0cd09bfb2650210b2d86da3536", node_type="VASP"),
    ]
    edges = [
        GraphEdge(source=victim_root, target="0x2910543af39aba0cd09bfb2650210b2d86da3536", transfer=Transfer(chain=Chain.ETHEREUM, source=victim_root, destination="0x2910543af39aba0cd09bfb2650210b2d86da3536", asset="ETH", amount="0.2", tx_hash="0xtx_kraken", provider="TEST_FIXTURE"), asset="ETH", amount="0.2", hop=1, timestamp=now),
        GraphEdge(source=victim_root, target="0xinter", transfer=Transfer(chain=Chain.ETHEREUM, source=victim_root, destination="0xinter", asset="ETH", amount="1.5", tx_hash="0xtx_inter", provider="TEST_FIXTURE"), asset="ETH", amount="1.5", hop=1, timestamp=now),
        GraphEdge(source="0xinter", target="0x28c6c06298d514db089934071355e5743bf21d60", transfer=Transfer(chain=Chain.ETHEREUM, source="0xinter", destination="0x28c6c06298d514db089934071355e5743bf21d60", asset="ETH", amount="1.5", tx_hash="0xtx_binance", provider="TEST_FIXTURE"), asset="ETH", amount="1.5", hop=2, timestamp=now + timedelta(minutes=15)),
    ]

    trace = TraceResult(
        case_id="case-test-proximity",
        root_address=victim_root,
        mode="DEVELOPMENT_FIXTURE",
        provider="DevelopmentFixture",
        nodes=nodes,
        edges=edges,
        signals=[],
        evidence=[],
    )

    engine = VASPProximityEngine(trace, sample_attributions)
    candidates = engine.evaluate_proximity()

    assert len(candidates) == 2
    # Binance (rank 1 due to 88%+ volume of victim funds & 0.98 confidence)
    assert candidates[0].entity_id == "vasp-binance"
    assert candidates[0].rank == 1
    assert candidates[0].hop_distance == 2
    assert candidates[0].percentage_of_victim_funds > 80.0

    # Kraken (rank 2)
    assert candidates[1].entity_id == "vasp-kraken"
    assert candidates[1].rank == 2
    assert candidates[1].hop_distance == 1


def test_time_to_vasp_and_fund_at_risk(sample_attributions):
    now = datetime.now(timezone.utc)
    victim_root = "0xvictim000000000000000000000000000000001"

    nodes = [
        GraphNode(id="n0", address=victim_root, node_type="WALLET"),
        GraphNode(id="n1", address="0xinter", node_type="WALLET"),
        GraphNode(id="n2", address="0x28c6c06298d514db089934071355e5743bf21d60", node_type="VASP"),
    ]
    edges = [
        GraphEdge(
            source=victim_root,
            target="0xinter",
            transfer=Transfer(chain=Chain.ETHEREUM, source=victim_root, destination="0xinter", asset="ETH", amount="3.0", tx_hash="0xtx_victim", provider="TEST_FIXTURE"),
            asset="ETH",
            amount="3.0",
            hop=1,
            timestamp=now,
        ),
        GraphEdge(
            source="0xinter",
            target="0x28c6c06298d514db089934071355e5743bf21d60",
            transfer=Transfer(chain=Chain.ETHEREUM, source="0xinter", destination="0x28c6c06298d514db089934071355e5743bf21d60", asset="ETH", amount="3.0", tx_hash="0xtx_fast", provider="TEST_FIXTURE"),
            asset="ETH",
            amount="3.0",
            hop=2,
            timestamp=now + timedelta(seconds=145),
        ),
    ]

    trace = TraceResult(
        case_id="case-test-ttv",
        root_address=victim_root,
        mode="DEVELOPMENT_FIXTURE",
        provider="DevelopmentFixture",
        nodes=nodes,
        edges=edges,
        signals=[],
        evidence=[],
    )

    engine = VASPProximityEngine(trace, sample_attributions)
    ttv = engine.calculate_time_to_vasp()

    assert ttv.case_id == "case-test-ttv"
    assert ttv.target_vasp_id == "vasp-binance"
    assert ttv.time_to_vasp_formatted in ("2m 25s", "2m 24s", "2m 26s", "145s")

    risk = engine.calculate_fund_at_risk()
    assert risk.total_victim_loss_usd == 9600.0  # 3.0 ETH * 3200
    assert risk.currently_actionable_vasp_exposure_usd == 9600.0
    assert "Investigative intelligence" in risk.disclaimer


def test_format_duration_seconds():
    assert format_duration_seconds(45) == "45s"
    assert format_duration_seconds(125) == "2m 5s"
    assert format_duration_seconds(3665) == "1h 1m"
    assert format_duration_seconds(90000) == "1d 1h"
    assert format_duration_seconds(None) == "N/A"
