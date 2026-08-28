from datetime import datetime, timezone, timedelta

import pytest

from app.domain import Chain, ConfidenceLevel, Transfer, BridgeDefinition, AssetIdentity, normalize_address
from app.cross_chain import ChainRegistry, BridgeRegistry, BridgeDetectionEngine, CrossChainCorrelationEngine, CrossChainGraphBuilder
from app.provider import TronGridProvider
from app.config import settings


ETH_A="0x"+"a"*40
ETH_BRIDGE="0x"+"b"*40
TRON_C="T"+"1"*33
TX1="0x"+"1"*64
TX2="2"*64


def transfer(chain, source, destination, tx, asset="USDT", timestamp=None):
    return Transfer(tx_hash=tx,chain=chain,source=source,destination=destination,asset=asset,amount="10",provider="fixture",timestamp=timestamp or datetime.now(timezone.utc),transfer_type="token",contract_address="0x"+"c"*40)


def test_chain_registry_keeps_chain_address_identity_distinct():
    registry=ChainRegistry.default()
    assert registry.get(Chain.ETHEREUM).native_asset=="ETH"
    assert registry.get(Chain.TRON).native_asset=="TRX"
    assert registry.node_id(Chain.ETHEREUM,"0x"+"1"*40)!=registry.node_id(Chain.TRON,"0x"+"1"*40)

def test_address_normalization_is_chain_specific():
    tron_address="T"+"a"*33
    assert normalize_address(Chain.ETHEREUM,"0x"+"A"*40)=="0x"+"a"*40
    assert normalize_address(Chain.TRON,tron_address)==tron_address
    assert ChainRegistry.default().node_id(Chain.TRON,tron_address).endswith(tron_address)


def test_bridge_detection_requires_curated_contract_definition():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},source="fixture",version="1")
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1)])[0]
    assert interaction.interaction_type=="BRIDGE_DEPOSIT"
    assert interaction.destination_chain is None
    assert "contract" in interaction.explanation.lower()


def test_correlation_is_strong_only_when_source_backed_signals_match():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},withdrawal_contracts={Chain.TRON:[TRON_C]},source="fixture",version="1")
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    deposit=transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1,timestamp=t)
    withdrawal=transfer(Chain.TRON,TRON_C,TRON_C,TX2,timestamp=t+timedelta(seconds=30))
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([deposit])[0].model_copy(update={"destination_chain":Chain.TRON,"recipient":TRON_C,"message_id":"m-1"})
    link=CrossChainCorrelationEngine().correlate([interaction],[withdrawal],definition)[0]
    assert link.correlation_level=="STRONG"
    assert link.confidence_band in {ConfidenceLevel.HIGH,ConfidenceLevel.CONFIRMED}
    assert any("destination" in reason for reason in link.correlation_reasons)


def test_cross_chain_graph_preserves_observed_and_inferred_edges():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},source="fixture",version="1")
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    observed=transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1,timestamp=t)
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([observed])[0].model_copy(update={"destination_chain":Chain.TRON,"recipient":TRON_C})
    withdrawal=transfer(Chain.TRON,TRON_C,TRON_C,TX2,timestamp=t+timedelta(seconds=30))
    link=CrossChainCorrelationEngine().correlate([interaction],[withdrawal],definition)[0]
    graph=CrossChainGraphBuilder().build([observed,withdrawal],[link],Chain.ETHEREUM,ETH_A)
    assert any(node.node_id==f"ethereum:{ETH_A}" for node in graph.nodes)
    assert any(node.node_id==f"tron:{TRON_C}" for node in graph.nodes)
    assert any(edge.edge_type=="CROSS_CHAIN_LINK" and edge.observed_or_inferred=="INFERRED" for edge in graph.edges)


def test_unresolved_correlation_is_not_promoted_to_fact():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},source="fixture",version="1")
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1,timestamp=t)])[0].model_copy(update={"destination_chain":Chain.TRON})
    withdrawal=transfer(Chain.TRON,TRON_C,TRON_C,TX2,timestamp=t+timedelta(days=2))
    link=CrossChainCorrelationEngine().correlate([interaction],[withdrawal],definition)[0]
    assert link.correlation_level in {"POSSIBLE","UNRESOLVED"}
    assert link.observed_or_inferred=="INFERRED"
    assert link.destination is None

def test_missing_destination_chain_does_not_correlate_by_timing_alone():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},source="fixture",version="1")
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1,timestamp=t)])[0]
    candidate=transfer(Chain.TRON,TRON_C,TRON_C,TX2,timestamp=t+timedelta(seconds=10))
    link=CrossChainCorrelationEngine().correlate([interaction],[candidate],definition)[0]
    assert link.correlation_level=="UNRESOLVED"
    assert link.destination is None

def test_repeated_cross_chain_correlation_has_stable_ids():
    definition=BridgeDefinition(bridge_id="bridge.test",name="Fixture Bridge",supported_chains=[Chain.ETHEREUM,Chain.TRON],deposit_contracts={Chain.ETHEREUM:[ETH_BRIDGE]},source="fixture",version="1")
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    deposit=transfer(Chain.ETHEREUM,ETH_A,ETH_BRIDGE,TX1,timestamp=t)
    interaction=BridgeDetectionEngine(BridgeRegistry([definition])).detect([deposit])[0].model_copy(update={"destination_chain":Chain.TRON,"recipient":TRON_C,"message_id":"m-1"})
    withdrawal=transfer(Chain.TRON,TRON_C,TRON_C,TX2,timestamp=t+timedelta(seconds=30))
    first=CrossChainCorrelationEngine().correlate([interaction],[withdrawal],definition)[0]
    second=CrossChainCorrelationEngine().correlate([interaction],[withdrawal],definition)[0]
    assert first.correlation_id==second.correlation_id
    assert first.link_id==second.link_id


def test_tron_provider_is_explicitly_not_configured_without_credentials(monkeypatch):
    monkeypatch.setattr(settings,"trongrid_api_key",None)
    capability=TronGridProvider().capabilities()[0]
    assert capability.status.value=="NOT_CONFIGURED"
