from datetime import datetime, timezone, timedelta
import pytest

from app.domain import (
    InvestigationCase,
    WalletCreate,
    Chain,
    TraceResult,
    GraphNode,
    GraphEdge,
    Transfer,
    TraceLimits,
    TraceMetrics,
    DataMode,
    BridgeDefinition,
    BridgeInteraction,
    ConfidenceLevel,
    VaspEntity,
    VaspBlockchainAddress,
    VaspClassification,
)
from app.cross_chain import (
    ChainRegistry,
    BridgeRegistry,
    BridgeDetectionEngine,
    CrossChainCorrelationEngine,
    CrossChainGraphBuilder,
)
from app.cross_chain_service import CrossChainService
from app.vasp_attribution_engine import VASPAttributionEngine

VICTIM_ETH = "0x1111111111111111111111111111111111111111"
BRIDGE_STARGATE_ETH = "0x8731d54e9d02c286767d56ac03e8037c07e01e98"
SUSPECT_TRON = "TStargateRecipientAddress111111111"
BINANCE_TRON_VASP = "TBinanceDepositProxyAddress111111"

SUSPECT_BSC = "0x2222222222222222222222222222222222222222"
COINBASE_BSC_VASP = "0x9999999999999999999999999999999999999999"


@pytest.fixture
def cross_chain_setup():
    chain_registry = ChainRegistry.default()
    bridge_registry = BridgeRegistry()
    detector = BridgeDetectionEngine(bridge_registry)
    correlation = CrossChainCorrelationEngine()
    graph_builder = CrossChainGraphBuilder(chain_registry)
    return {
        "chain_registry": chain_registry,
        "bridge_registry": bridge_registry,
        "detector": detector,
        "correlation": correlation,
        "graph_builder": graph_builder,
    }


def test_chain_aware_identity(cross_chain_setup):
    """
    Verify that ETH:0x111... and BSC:0x111... are distinct identities.
    """
    chain_reg = cross_chain_setup["chain_registry"]
    node_eth = chain_reg.node_id(Chain.ETHEREUM, "0x1111111111111111111111111111111111111111")
    node_bsc = chain_reg.node_id(Chain.BSC, "0x1111111111111111111111111111111111111111")
    assert node_eth == "ethereum:0x1111111111111111111111111111111111111111"
    assert node_bsc == "bsc:0x1111111111111111111111111111111111111111"
    assert node_eth != node_bsc


def test_eth_to_tron_bridge_detection_and_correlation(cross_chain_setup):
    """
    Test synthetic ETH -> TRON cross-chain bridge interaction & correlation.
    """
    now = datetime.now(timezone.utc)
    detector = cross_chain_setup["detector"]
    correlation = cross_chain_setup["correlation"]

    source_transfer = Transfer(
        tx_hash="0xa100000000000000000000000000000000000000000000000000000000000001",
        chain=Chain.ETHEREUM,
        timestamp=now,
        source=VICTIM_ETH,
        destination=BRIDGE_STARGATE_ETH,
        asset="USDT",
        amount="5000.0",
        provider="FIXTURE",
        raw_reference={
            "cross_chain_observation": {
                "destination_chain": Chain.TRON,
                "destination_address": SUSPECT_TRON,
                "message_id": "msg-12345",
            }
        },
    )

    dest_transfer = Transfer(
        tx_hash="0xtron000000000000000000000000000000000000000000000000000000000001",
        chain=Chain.TRON,
        timestamp=now + timedelta(seconds=120),
        source=BRIDGE_STARGATE_ETH,
        destination=SUSPECT_TRON,
        asset="USDT",
        amount="5000.0",
        provider="FIXTURE",
        raw_reference={"message_id": "msg-12345"},
    )

    interactions = detector.detect([source_transfer])
    assert len(interactions) == 1
    assert interactions[0].bridge_id == "bridge-stargate"
    assert interactions[0].source_chain == Chain.ETHEREUM

    links = correlation.correlate(interactions, [dest_transfer])
    assert len(links) == 1
    link = links[0]
    assert link.correlation_level in {"EXACT", "STRONG"}
    assert link.source.chain == Chain.ETHEREUM
    assert link.destination.chain == Chain.TRON
    assert link.destination.address == SUSPECT_TRON


def test_eth_to_bsc_bridge_detection_and_correlation(cross_chain_setup):
    """
    Test synthetic ETH -> BSC cross-chain bridge interaction.
    """
    now = datetime.now(timezone.utc)
    detector = cross_chain_setup["detector"]
    correlation = cross_chain_setup["correlation"]

    source_transfer = Transfer(
        tx_hash="0xa200000000000000000000000000000000000000000000000000000000000002",
        chain=Chain.ETHEREUM,
        timestamp=now,
        source=VICTIM_ETH,
        destination=BRIDGE_STARGATE_ETH,
        asset="USDC",
        amount="10000.0",
        provider="FIXTURE",
        raw_reference={
            "cross_chain_observation": {
                "destination_chain": Chain.BSC,
                "destination_address": SUSPECT_BSC,
                "message_id": "msg-67890",
            }
        },
    )

    dest_transfer = Transfer(
        tx_hash="0xbsc0000000000000000000000000000000000000000000000000000000000001",
        chain=Chain.BSC,
        timestamp=now + timedelta(seconds=180),
        source=BRIDGE_STARGATE_ETH,
        destination=SUSPECT_BSC,
        asset="USDC",
        amount="10000.0",
        provider="FIXTURE",
        raw_reference={"message_id": "msg-67890"},
    )

    interactions = detector.detect([source_transfer])
    links = correlation.correlate(interactions, [dest_transfer])
    assert len(links) == 1
    assert links[0].destination.chain == Chain.BSC
    assert links[0].destination.address == SUSPECT_BSC


def test_missing_destination_transaction_unresolved(cross_chain_setup):
    """
    Verify missing destination transaction produces an UNRESOLVED link without guessing.
    """
    now = datetime.now(timezone.utc)
    detector = cross_chain_setup["detector"]
    correlation = cross_chain_setup["correlation"]

    source_transfer = Transfer(
        tx_hash="0xa300000000000000000000000000000000000000000000000000000000000003",
        chain=Chain.ETHEREUM,
        timestamp=now,
        source=VICTIM_ETH,
        destination=BRIDGE_STARGATE_ETH,
        asset="USDT",
        amount="2500.0",
        provider="FIXTURE",
        raw_reference={"cross_chain_observation": {"destination_chain": Chain.TRON}},
    )

    interactions = detector.detect([source_transfer])
    links = correlation.correlate(interactions, [])  # No destination transfers available
    assert len(links) == 1
    assert links[0].correlation_level == "UNRESOLVED"
    assert links[0].destination is None


def test_delayed_destination_transaction(cross_chain_setup):
    """
    Test correlation when destination transaction occurs after a 2-hour delay.
    """
    now = datetime.now(timezone.utc)
    detector = cross_chain_setup["detector"]
    correlation = cross_chain_setup["correlation"]

    source_transfer = Transfer(
        tx_hash="0xa400000000000000000000000000000000000000000000000000000000000004",
        chain=Chain.ETHEREUM,
        timestamp=now,
        source=VICTIM_ETH,
        destination=BRIDGE_STARGATE_ETH,
        asset="USDT",
        amount="8000.0",
        provider="FIXTURE",
        raw_reference={
            "cross_chain_observation": {
                "destination_chain": Chain.TRON,
                "destination_address": SUSPECT_TRON,
                "message_id": "msg-delayed-999",
            }
        },
    )

    delayed_dest_transfer = Transfer(
        tx_hash="0xtron0000000000000000000000000000000000000000000000000000000000099",
        chain=Chain.TRON,
        timestamp=now + timedelta(hours=2),
        source=BRIDGE_STARGATE_ETH,
        destination=SUSPECT_TRON,
        asset="USDT",
        amount="8000.0",
        provider="FIXTURE",
        raw_reference={"message_id": "msg-delayed-999"},
    )

    interactions = detector.detect([source_transfer])
    links = correlation.correlate(interactions, [delayed_dest_transfer])
    assert len(links) == 1
    assert links[0].correlation_level in {"EXACT", "STRONG"}


def test_ambiguous_bridge_attribution(cross_chain_setup):
    """
    Test ranking when multiple destination candidate transfers exist.
    """
    now = datetime.now(timezone.utc)
    detector = cross_chain_setup["detector"]
    correlation = cross_chain_setup["correlation"]

    source_transfer = Transfer(
        tx_hash="0xa500000000000000000000000000000000000000000000000000000000000005",
        chain=Chain.ETHEREUM,
        timestamp=now,
        source=VICTIM_ETH,
        destination=BRIDGE_STARGATE_ETH,
        asset="USDT",
        amount="1000.0",
        provider="FIXTURE",
        raw_reference={
            "cross_chain_observation": {
                "destination_chain": Chain.TRON,
                "destination_address": SUSPECT_TRON,
                "message_id": "msg-target-correct",
            }
        },
    )

    # Candidate 1: Weak match (no message ID match)
    cand1 = Transfer(
        tx_hash="0xtron_wrong_1",
        chain=Chain.TRON,
        timestamp=now + timedelta(minutes=10),
        source=BRIDGE_STARGATE_ETH,
        destination="TAnotherAddress11111111111111111111",
        asset="USDT",
        amount="1000.0",
        provider="FIXTURE",
    )

    # Candidate 2: Strong match (matching message ID & destination address)
    cand2 = Transfer(
        tx_hash="0xtron_correct_2",
        chain=Chain.TRON,
        timestamp=now + timedelta(minutes=2),
        source=BRIDGE_STARGATE_ETH,
        destination=SUSPECT_TRON,
        asset="USDT",
        amount="1000.0",
        provider="FIXTURE",
        raw_reference={"message_id": "msg-target-correct"},
    )

    interactions = detector.detect([source_transfer])
    links = correlation.correlate(interactions, [cand1, cand2])
    assert len(links) == 1
    assert links[0].destination_transaction_hash == "0xtron_correct_2"


def test_vasp_attribution_across_bridge_hop():
    """
    Verify VASPAttributionEngine attributes Binance TRON VASP across bridge hop without address conflation.
    """
    binance = VaspEntity(
        id="vasp-binance",
        legal_name="Binance Holdings Ltd",
        trading_name="Binance",
        entity_type="VASP",
    )
    binance_tron_addr = VaspBlockchainAddress(
        id="addr-binance-tron",
        chain=Chain.TRON,
        address=BINANCE_TRON_VASP,
        entity_id="vasp-binance",
        address_type="DEPOSIT_ADDRESS",
    )

    engine = VASPAttributionEngine(
        entities=[binance],
        addresses=[binance_tron_addr],
        clusters=[],
    )

    # Analyze Binance TRON deposit address directly on TRON
    res = engine.analyze(Chain.TRON, BINANCE_TRON_VASP)
    assert res.classification in {VaspClassification.KNOWN, VaspClassification.PROBABLE}
    assert res.candidate_entity.trading_name == "Binance"

    # Analyze Ethereum victim address: should NOT match Binance TRON address directly due to chain isolation
    res_eth = engine.analyze(Chain.ETHEREUM, BINANCE_TRON_VASP)
    assert res_eth.classification == VaspClassification.UNKNOWN
