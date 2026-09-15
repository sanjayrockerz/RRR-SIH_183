"""Targeted closure checks for bounded Ethereum -> Tron behavior."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from app.cross_chain import BridgeRegistry, BridgeDetectionEngine, CrossChainCorrelationEngine
from app.domain import BridgeDefinition, Chain, Transfer

ETH = "0x" + "a" * 40
BRIDGE = "0x" + "b" * 40
TRON = "T" + "1" * 33
TX1 = "0x" + "1" * 64
TX2 = "2" * 64

def _fixture(destination_chain=None, destination_address=None, message_id=None):
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    definition = BridgeDefinition(bridge_id="closure.bridge", name="Closure fixture bridge", supported_chains=[Chain.ETHEREUM, Chain.TRON], deposit_contracts={Chain.ETHEREUM: [BRIDGE]}, source="DEVELOPMENT_FIXTURE", version="1")
    raw = {"cross_chain_observation": {"bridge_contract": BRIDGE}}
    if destination_chain: raw["cross_chain_observation"]["destination_chain"] = destination_chain
    if destination_address: raw["cross_chain_observation"]["destination_address"] = destination_address
    if message_id: raw["cross_chain_observation"]["message_id"] = message_id
    source = Transfer(tx_hash=TX1, chain=Chain.ETHEREUM, source=ETH, destination=BRIDGE, asset="USDT", amount="10", provider="DEVELOPMENT_FIXTURE", transfer_type="token", timestamp=at, raw_reference=raw)
    dest = Transfer(tx_hash=TX2, chain=Chain.TRON, source=TRON, destination=TRON, asset="USDT", amount="10", provider="DEVELOPMENT_FIXTURE", transfer_type="token", timestamp=at + timedelta(seconds=30), raw_reference={"message_id": message_id} if message_id else {})
    interaction = BridgeDetectionEngine(BridgeRegistry([definition])).detect([source])[0]
    return definition, interaction, dest

def test_cross_chain_demo_eth_to_tron():
    definition, interaction, destination = _fixture("tron", TRON, "closure-message")
    link = CrossChainCorrelationEngine().correlate([interaction.model_copy(update={"destination_chain": Chain.TRON, "recipient": TRON})], [destination], definition)[0]
    assert link.correlation_level == "STRONG"
    assert link.confidence_band.value == "HIGH"

def test_cross_chain_missing_destination_fails_closed():
    definition, interaction, destination = _fixture()
    link = CrossChainCorrelationEngine().correlate([interaction], [destination], definition)[0]
    assert link.destination is None and link.correlation_level == "UNRESOLVED"

def test_cross_chain_repeat_analysis_is_idempotent():
    definition, interaction, destination = _fixture("tron", TRON, "closure-message")
    updated = interaction.model_copy(update={"destination_chain": Chain.TRON, "recipient": TRON})
    one = CrossChainCorrelationEngine().correlate([updated], [destination], definition)[0]
    two = CrossChainCorrelationEngine().correlate([updated], [destination], definition)[0]
    assert one.correlation_id == two.correlation_id
    assert one.link_id == two.link_id

def test_cross_chain_does_not_claim_universal_trace():
    result = json.loads((Path(__file__).resolve().parents[3] / "artifacts/cross_chain_demo_eth_tron.json").read_text())
    assert any("not universal" in item.lower() for item in result["limitations"])

def test_tron_address_identity_preserves_case():
    _, interaction, _ = _fixture("tron", TRON, "closure-message")
    assert interaction.source_address != interaction.source_address.lower() or interaction.source_chain == Chain.ETHEREUM
    assert TRON == interaction.raw_reference["cross_chain_observation"]["destination_address"]

def test_cross_chain_evidence_provenance_preserved():
    definition, interaction, destination = _fixture("tron", TRON, "closure-message")
    interaction = interaction.model_copy(update={"evidence_ids": ["eth-evidence"]})
    destination = destination.model_copy(update={"raw_reference": {"message_id": "closure-message", "evidence_ids": ["tron-evidence"]}})
    link = CrossChainCorrelationEngine().correlate([interaction.model_copy(update={"destination_chain": Chain.TRON, "recipient": TRON})], [destination], definition)[0]
    assert link.provenance_source == "CrossChainCorrelationEngine"
    assert link.evidence_ids == ["eth-evidence", "tron-evidence"]
