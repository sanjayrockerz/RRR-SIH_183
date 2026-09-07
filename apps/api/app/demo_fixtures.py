"""Deterministic DEVELOPMENT_SYNTHETIC investigation fixtures.

These definitions are deliberately separate from provider acquisition. They exercise
the normal PostgreSQL trace, evidence, pattern, risk, and graph read paths.
"""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
import hashlib
from .domain import *

DEMO_ROOT = "0x1111111111111111111111111111111111111111"
DEMO_VASP = "0x9999999999999999999999999999999999999999"
DEMO_MIXER = "0x6666666666666666666666666666666666666666"
DEMO_BRIDGE = "0x7777777777777777777777777777777777777777"

def _address(ref: str, name: str) -> str:
    return "0x" + hashlib.sha256(f"DEVELOPMENT_SYNTHETIC:{ref}:{name}".encode()).hexdigest()[:40]

def _risk_config(weights: list[tuple[str, str, float]]) -> RiskScoringConfig:
    defs = []
    for definition_id, name, weight in weights:
        defs.append(RiskFactorDefinition(id=definition_id, name=name, category="DEVELOPMENT_SYNTHETIC", default_weight=weight, max_contribution=weight, explanation_template=f"{name} is supported by {{count}} persisted synthetic observation(s)." if definition_id.startswith("pattern:") else f"{name} is supported by {{count}} attributed endpoint(s)."))
    return RiskScoringConfig(version="development-synthetic-fixture-v1", factors=defs, thresholds=RiskBandThresholds(guarded_min=25, elevated_min=50, high_min=60, critical_min=90))

def fixture_specs():
    return [
        {"reference":"CASE-MIXER-001", "title":"Suspected Investment Fraud — Mixer Laundering", "fraud_type":"Investment fraud", "root":DEMO_ROOT, "risk":94, "node_names":["ROOT WALLET","INTERMEDIARY 1","INTERMEDIARY 2","MIXER","INTERMEDIARY 3","VASP / EXCHANGE"], "node_types":["ROOT","INTERMEDIARY","INTERMEDIARY","MIXER","INTERMEDIARY","VASP"], "addresses":[DEMO_ROOT,_address("CASE-MIXER-001","hop1"),_address("CASE-MIXER-001","hop2"),DEMO_MIXER,_address("CASE-MIXER-001","hop3"),DEMO_VASP], "amounts":["12.40","12.10","11.95","11.70","11.55"], "asset":"ETH", "chain":Chain.ETHEREUM, "risk_weights":[("pattern:rapid_hop","Rapid multi-hop movement",30), ("pattern:mixer_interaction","Mixer interaction",30), ("pattern:peel_chain","Layering through intermediary wallets",30), ("pattern:consolidation","High-value transfer",30), ("entity:vasp","VASP exposure",26.64)], "pattern_types":[PatternType.RAPID_HOP,PatternType.MIXER_INTERACTION,PatternType.PEEL_CHAIN,PatternType.CONSOLIDATION]},
        {"reference":"CASE-CROSSCHAIN-001", "title":"Cross-Chain Obfuscation Investigation", "fraud_type":"Cross-chain obfuscation", "root":_address("CASE-CROSSCHAIN-001","eth-root"), "risk":87, "node_names":["ETH ROOT","ETH INTERMEDIARY","BRIDGE","TRON DESTINATION","TRON INTERMEDIARY","VASP / EXCHANGE"], "node_types":["ROOT","INTERMEDIARY","BRIDGE","INTERMEDIARY","INTERMEDIARY","VASP"], "addresses":[_address("CASE-CROSSCHAIN-001","eth-root"),_address("CASE-CROSSCHAIN-001","eth-hop"),DEMO_BRIDGE,_address("CASE-CROSSCHAIN-001","tron-destination"),_address("CASE-CROSSCHAIN-001","tron-hop"),DEMO_VASP], "amounts":["8.00","7.80","7.80","7.55","7.40"], "asset":"ETH", "chain":Chain.ETHEREUM, "risk_weights":[("pattern:rapid_hop","Rapid movement",27), ("pattern:bridge_hop","Cross-chain bridge movement",27), ("pattern:cross_chain_hop","Cross-chain transition",27), ("pattern:peel_chain","Cross-chain layering",27), ("entity:vasp","VASP exposure",27.72)], "pattern_types":[PatternType.RAPID_HOP,PatternType.BRIDGE_HOP,PatternType.CROSS_CHAIN_HOP,PatternType.PEEL_CHAIN], "cross_chain":True},
        {"reference":"CASE-VASP-001", "title":"Suspicious Fund Consolidation — VASP Exit", "fraud_type":"Suspicious fund consolidation", "root":_address("CASE-VASP-001","root"), "risk":72, "node_names":["ROOT WALLET","INTERMEDIARY 1","INTERMEDIARY 2","INTERMEDIARY 3","VASP / EXCHANGE"], "node_types":["ROOT","INTERMEDIARY","INTERMEDIARY","INTERMEDIARY","VASP"], "addresses":[_address("CASE-VASP-001","root"),_address("CASE-VASP-001","hop1"),_address("CASE-VASP-001","hop2"),_address("CASE-VASP-001","hop3"),DEMO_VASP], "amounts":["6.00","5.85","5.70","5.55"], "asset":"ETH", "chain":Chain.ETHEREUM, "risk_weights":[("pattern:rapid_hop","Rapid movement",28), ("pattern:fan_in","Fund consolidation",28), ("pattern:peel_chain","Intermediary chaining",28), ("entity:vasp","VASP exposure",28.32)], "pattern_types":[PatternType.RAPID_HOP,PatternType.FAN_IN,PatternType.PEEL_CHAIN]},
    ]

def build_fixture(spec: dict, case_id: str) -> tuple[TraceResult, list[PatternObservation], RiskScoringConfig, dict]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    addresses = spec["addresses"]
    edges=[]; evidence=[]; nodes=[]
    for i, address in enumerate(addresses):
        node_type=spec["node_types"][i]
        chain = Chain.TRON if spec.get("cross_chain") and i >= 3 else Chain.ETHEREUM
        entity_name="Demo Mixer Service" if node_type=="MIXER" else ("Demo Exchange" if node_type=="VASP" else None)
        risk_level="CRITICAL" if spec["risk"]>=90 else ("HIGH" if spec["risk"]>=50 else "LOW")
        nodes.append(GraphNode(id=address,address=address,chain=chain,depth=i,node_type=node_type,transaction_count=(1 if i in {0,len(addresses)-1} else 2),entity_name=entity_name,entity_type=node_type,risk_score=94 if i==0 and spec["risk"]==94 else spec["risk"],risk_level=risk_level,is_root=i==0,is_endpoint=i==len(addresses)-1,position={"x":100+i*200,"y":300},metadata={"label":spec["node_names"][i],"entity_name":entity_name,"entity_type":node_type,"risk_score":spec["risk"],"risk_level":risk_level,"is_root":i==0,"is_endpoint":i==len(addresses)-1,"position":{"x":100+i*200,"y":300}}))
    for i, amount in enumerate(spec["amounts"]):
        source,destination=addresses[i],addresses[i+1]
        # The bridge deposit remains on Ethereum; the first destination-chain
        # transfer begins on Tron after the bridge boundary.
        edge_chain = Chain.TRON if spec.get("cross_chain") and i >= 3 else Chain.ETHEREUM
        tx_hash="0x"+uuid5(NAMESPACE_URL,f"{spec['reference']}:{case_id}:TX-{i+1}").hex*2
        raw={"source_mode":"DEVELOPMENT_SYNTHETIC","fixture_id":spec["reference"],"transaction_id":f"{spec['reference']}-TX-{i+1}","node_labels":{source:spec["node_names"][i],destination:spec["node_names"][i+1]},"node_types":{source:spec["node_types"][i],destination:spec["node_types"][i+1]},"source_chain": "Ethereum", "destination_chain": "Tron" if spec.get("cross_chain") and i==2 else edge_chain.value}
        if spec.get("cross_chain") and i in {2, 3}:
            raw["message_id"] = f"{spec['reference']}-MESSAGE-001"
        transfer=Transfer(tx_hash=tx_hash,chain=edge_chain,block_number=24000000+i,timestamp=base+timedelta(minutes=i),source=source,destination=destination,asset=spec["asset"],amount=amount,value_native=float(amount),provider="DEVELOPMENT SYNTHETIC",transfer_type="contract" if spec["node_types"][i+1] in {"MIXER","BRIDGE"} else "native",contract_address=destination if spec["node_types"][i+1] in {"MIXER","BRIDGE"} else None,raw_reference=raw)
        evidence_id=str(uuid5(NAMESPACE_URL,f"{tx_hash}:evidence"))
        evidence.append(Evidence(evidence_id=evidence_id,case_id=case_id,type="TRANSACTION",chain=edge_chain,tx_hash=tx_hash,source="DEVELOPMENT_SYNTHETIC",captured_at=transfer.timestamp,metadata={"fixture":spec["reference"],"transaction_id":raw["transaction_id"]},integrity_status="VERIFIED"))
        edges.append(GraphEdge(edge_id=f"{spec['reference']}:EDGE-{i+1}",source=source,target=destination,transfer=transfer,hop=i+1,transaction_hash=tx_hash,evidence_id=evidence_id))
    path=addresses[:]
    trace=TraceResult(case_id=case_id,trace_id=str(uuid5(NAMESPACE_URL,f"{spec['reference']}:{case_id}:trace")),root_address=spec["root"],mode=DataMode.DEVELOPMENT_FIXTURE,provider="DEVELOPMENT SYNTHETIC",nodes=nodes,edges=edges,signals=[],evidence=evidence,limits=TraceLimits(max_hops=8,max_nodes=100,max_edges=500,max_transactions=500,max_duration=60),metrics=TraceMetrics(node_count=len(nodes),edge_count=len(edges),unique_wallet_count=len(nodes),maximum_hop=len(edges),path_count=1,unique_transaction_count=len(edges),unique_asset_count=1),predominant_path=path,paths=[TransactionPath(path_id=f"{spec['reference']}:PATH",node_ids=path,edges=edges)],acquisition=AcquisitionStatistics(discovered=len(edges),normalized=len(edges),persisted=len(edges),provider="DEVELOPMENT SYNTHETIC",mode=DataMode.DEVELOPMENT_FIXTURE,retrieved_at=base))
    patterns=[]
    for i, pattern_type in enumerate(spec["pattern_types"]):
        patterns.append(PatternObservation(pattern_id=str(uuid5(NAMESPACE_URL,f"{spec['reference']}:pattern:{i}")),case_id=case_id,trace_id=trace.trace_id,pattern_type=pattern_type,status=PatternStatus.OBSERVED,confidence_level=ConfidenceLevel.HIGH,severity=PatternSeverity.HIGH,description=f"{spec['node_names'][0]} shows {pattern_type}.",explanation=f"DEVELOPMENT_SYNTHETIC evidence supports {pattern_type} across the selected predominant path.",observed_at=edges[-1].transfer.timestamp,affected_nodes=path,affected_edges=[e.edge_id for e in edges],transaction_hashes=[e.transaction_hash for e in edges],evidence_ids=[e.evidence_id for e in evidence],metadata={"source_mode":"DEVELOPMENT_SYNTHETIC","risk_factor":spec["risk_weights"][i][1]},fingerprint=f"{spec['reference']}:pattern:{i}"))
    validate_fixture(trace)
    return trace,patterns,_risk_config(spec["risk_weights"]),{"positions":{f"{n.chain.value}:{n.address.lower()}":n.metadata["position"] for n in nodes},"viewport":{"scale":1,"panX":0,"panY":0}}

def validate_fixture(trace: TraceResult):
    node_keys={n.address.lower() for n in trace.nodes}; path=trace.predominant_path
    assert path and len(path)==len(set(path)), "predominant path must be non-empty and duplicate-free"
    assert len(path)==len(trace.edges)+1 and path[0].lower()==trace.root_address.lower(), "predominant path does not match route"
    for i, edge in enumerate(trace.edges):
        assert edge.source.lower() in node_keys and edge.target.lower() in node_keys, "edge references missing node"
        assert edge.source==path[i] and edge.target==path[i+1], "predominant edge direction is incorrect"
        assert edge.transfer.tx_hash and edge.transfer.amount and edge.transfer.asset and edge.transfer.timestamp, "transaction fields missing"
        assert edge.amount==edge.transfer.amount and edge.asset==edge.transfer.asset, "edge/transaction value mismatch"
    endpoint=next(n for n in trace.nodes if n.address.lower()==path[-1].lower())
    assert endpoint.metadata.get("is_endpoint") and endpoint.node_type=="VASP" and DEMO_VASP.lower()==endpoint.address.lower(), "invalid VASP endpoint"
