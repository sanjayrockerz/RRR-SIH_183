"""Generate the bounded, deterministic Ethereum -> Tron demo result.

This script uses the same bridge detection and correlation classes as the API.
It never calls a provider and never labels the fixture as observed live data.
"""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.cross_chain import BridgeRegistry, BridgeDetectionEngine, CrossChainCorrelationEngine
from app.domain import BridgeDefinition, Chain, Transfer
OUT = ROOT / "artifacts" / "cross_chain_demo_eth_tron.json"
ETH_SOURCE = "0x" + "a" * 40
ETH_BRIDGE = "0x" + "b" * 40
TRON_DESTINATION = "T" + "1" * 33
SOURCE_TX = "0x" + "1" * 64
DEST_TX = "2" * 64
EVIDENCE = ["RRR-DEMO-CROSSCHAIN-001:ETH-SOURCE", "RRR-DEMO-CROSSCHAIN-001:TRON-CONTINUATION"]


def main():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    definition = BridgeDefinition(
        bridge_id="RRR-DEMO-BRIDGE-001", name="RRR Development Synthetic Bridge",
        supported_chains=[Chain.ETHEREUM, Chain.TRON],
        deposit_contracts={Chain.ETHEREUM: [ETH_BRIDGE]},
        source="DEVELOPMENT_FIXTURE", version="rrr-demo-crosschain-v1",
    )
    source = Transfer(tx_hash=SOURCE_TX, chain=Chain.ETHEREUM, source=ETH_SOURCE,
                      destination=ETH_BRIDGE, asset="USDT", amount="1000",
                      provider="DEVELOPMENT_FIXTURE", transfer_type="token",
                      timestamp=timestamp, contract_address="0x" + "c" * 40,
                      raw_reference={"cross_chain_observation": {
                          "destination_chain": "tron", "destination_address": TRON_DESTINATION,
                          "message_id": "RRR-DEMO-MESSAGE-001", "evidence_ids": [EVIDENCE[0]],
                          "bridge_contract": ETH_BRIDGE,
                      }})
    destination = Transfer(tx_hash=DEST_TX, chain=Chain.TRON, source=TRON_DESTINATION,
                           destination=TRON_DESTINATION, asset="USDT", amount="1000",
                           provider="DEVELOPMENT_FIXTURE", transfer_type="token",
                           timestamp=timestamp + timedelta(seconds=30),
                           contract_address="T" + "2" * 33,
                           raw_reference={"message_id": "RRR-DEMO-MESSAGE-001", "evidence_ids": [EVIDENCE[1]]})
    interaction = BridgeDetectionEngine(BridgeRegistry([definition])).detect([source])[0]
    link = CrossChainCorrelationEngine().correlate(
        [interaction.model_copy(update={"destination_chain": Chain.TRON, "recipient": TRON_DESTINATION})],
        [destination], definition,
    )[0]
    result = {
        "fixture": "RRR-DEMO-CROSSCHAIN-001", "source_chain": "ethereum", "destination_chain": "tron",
        "source_tx": SOURCE_TX, "bridge": definition.bridge_id,
        "correlation": {"status": link.correlation_level, "confidence": link.confidence_score,
                         "confidence_label": link.confidence_band.value, "reasons": link.correlation_reasons},
        "destination_tx": DEST_TX,
        "vasp_candidate": {"state": "UNKNOWN / UNRESOLVED", "name": None,
                            "reason": "No source-backed VASP attribution is present in this fixture."},
        "evidence_refs": EVIDENCE, "provenance": "DEVELOPMENT_FIXTURE",
        "limitations": ["Deterministic fixture; not live provider evidence.", "Bounded Ethereum-to-Tron correlation only; not universal cross-chain tracing.", "VASP attribution remains unresolved without source-backed entity evidence."],
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
