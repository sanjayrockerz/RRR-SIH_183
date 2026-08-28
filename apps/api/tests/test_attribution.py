from datetime import datetime, timezone
from app.attribution import AttributionEngine, NearestEntityResolver
from app.primary_path import select_primary_path
from app.synthetic_attribution import merge as merge_synthetic_attribution, DEMO_VASP_ADDRESS
from app.domain import *

ROOT="0x"+"a"*40; EXCHANGE="0x"+"b"*40; OTHER="0x"+"c"*40
def catalog():
    entity_a=Entity(entity_id="entity-a",name="Test Exchange",entity_type=EntityType.EXCHANGE)
    entity_b=Entity(entity_id="entity-b",name="Conflicting Service",entity_type=EntityType.SERVICE)
    sources=[AttributionSource(source_id="official",name="Test Fixture Official",source_type="TEST_FIXTURE",reference="fixture://official",reliability_level=ConfidenceLevel.CONFIRMED),AttributionSource(source_id="community",name="Test Fixture Community",source_type="TEST_FIXTURE",reference="fixture://community",reliability_level=ConfidenceLevel.LOW)]
    records=[AddressAttribution(attribution_id="a1",chain=Chain.ETHEREUM,address=EXCHANGE,entity_id="entity-a",role=AttributionRole.DEPOSIT,confidence=ConfidenceLevel.HIGH,source_id="official",source_reference="fixture://official"),AddressAttribution(attribution_id="a2",chain=Chain.ETHEREUM,address=EXCHANGE,entity_id="entity-b",role=AttributionRole.SERVICE,confidence=ConfidenceLevel.LOW,source_id="community",source_reference="fixture://community")]
    return [entity_a,entity_b],sources,records
def edge(tx,source,target):
    t=Transfer(tx_hash="0x"+tx*64,chain=Chain.ETHEREUM,source=source,destination=target,asset="ETH",amount="1",provider="fixture")
    return GraphEdge(edge_id=tx,source=source,target=target,transfer=t,hop=1,transaction_hash=t.tx_hash,evidence_id="ev-"+tx)
def test_conflicts_are_preserved_and_not_selected():
    entities,sources,records=catalog(); result=AttributionEngine(entities,sources,records).resolve(Chain.ETHEREUM,EXCHANGE)
    assert result.conflict and result.selected_entity_id is None and len(result.candidates)==2
def test_temporal_attribution_excludes_out_of_window():
    entities,sources,records=catalog(); records[0].first_seen=datetime(2025,1,1,tzinfo=timezone.utc)
    result=AttributionEngine(entities,sources,records).resolve(Chain.ETHEREUM,EXCHANGE,datetime(2024,1,1,tzinfo=timezone.utc))
    assert len(result.candidates)==1 and result.candidates[0].entity.entity_id=="entity-b"
def test_nearest_result_uses_graph_hop_and_path_evidence():
    entities,sources,records=catalog(); e1=edge("1",ROOT,OTHER); e2=edge("2",OTHER,EXCHANGE)
    trace=TraceResult(case_id="case",trace_id="trace",root_address=ROOT,mode=DataMode.HISTORICAL,provider="fixture",nodes=[GraphNode(id=ROOT,address=ROOT,depth=0),GraphNode(id=OTHER,address=OTHER,depth=1),GraphNode(id=EXCHANGE,address=EXCHANGE,depth=2)],edges=[e1,e2],signals=[],evidence=[Evidence(evidence_id="ev-1",case_id="case",type="TRANSACTION",chain=Chain.ETHEREUM,tx_hash=e1.transaction_hash,source="fixture",captured_at=datetime.now(timezone.utc)),Evidence(evidence_id="ev-2",case_id="case",type="TRANSACTION",chain=Chain.ETHEREUM,tx_hash=e2.transaction_hash,source="fixture",captured_at=datetime.now(timezone.utc))],paths=[TransactionPath(path_id="path",node_ids=[ROOT,OTHER,EXCHANGE],edges=[e1,e2])])
    result=NearestEntityResolver(AttributionEngine(entities,sources,records)).resolve(trace)
    assert result[0].hop_distance==2 and len(result[0].evidence)==2 and result[0].role==AttributionRole.DEPOSIT

def test_primary_path_stops_at_nearest_attributed_vasp():
    entities, sources, records = catalog()
    records = [item for item in records if item.entity_id == "entity-a"]
    far = "0x" + "d" * 40
    records.append(AddressAttribution(attribution_id="a3", chain=Chain.ETHEREUM, address=far, entity_id="entity-a", role=AttributionRole.DEPOSIT_ADDRESS, confidence=ConfidenceLevel.CONFIRMED, source_id="official", source_reference="fixture://official"))
    e1, e2 = edge("1", ROOT, OTHER), edge("2", OTHER, EXCHANGE)
    e3 = edge("3", EXCHANGE, far)
    trace = TraceResult(case_id="case", trace_id="trace", root_address=ROOT, mode=DataMode.HISTORICAL, provider="fixture", nodes=[GraphNode(id=x, address=x, depth=i) for i, x in enumerate([ROOT, OTHER, EXCHANGE, far])], edges=[e1, e2, e3], signals=[], evidence=[])
    primary = select_primary_path(trace, entities, sources, records)
    assert primary["terminal_entity_name"] == "Test Exchange"
    assert primary["hops"] == 2
    assert primary["transaction_hashes"] == [e1.transaction_hash, e2.transaction_hash]

def test_primary_path_does_not_fabricate_unknown_attribution():
    entities, sources, records = catalog()
    e1 = edge("1", ROOT, OTHER)
    trace = TraceResult(case_id="case", trace_id="trace", root_address=ROOT, mode=DataMode.HISTORICAL, provider="fixture", nodes=[GraphNode(id=ROOT, address=ROOT, depth=0), GraphNode(id=OTHER, address=OTHER, depth=1)], edges=[e1], signals=[], evidence=[])
    primary = select_primary_path(trace, entities, sources, records)
    assert primary["status"] == "UNATTRIBUTED"
    assert primary["terminal_entity_name"] == "UNKNOWN / UNATTRIBUTED DESTINATION"

def test_primary_path_is_chronological_and_reports_measurements():
    entities, sources, records = catalog()
    first = edge("1", ROOT, OTHER).model_copy(update={"transfer": edge("1", ROOT, OTHER).transfer.model_copy(update={"amount": "0.7500", "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc)})})
    terminal = edge("2", OTHER, EXCHANGE).model_copy(update={"transfer": edge("2", OTHER, EXCHANGE).transfer.model_copy(update={"amount": "1.160", "asset": "USDT", "timestamp": datetime(2025, 1, 2, tzinfo=timezone.utc)})})
    late_reverse = edge("3", EXCHANGE, OTHER).model_copy(update={"transfer": edge("3", EXCHANGE, OTHER).transfer.model_copy(update={"timestamp": datetime(2024, 12, 1, tzinfo=timezone.utc)})})
    trace = TraceResult(case_id="case", trace_id="trace", root_address=ROOT, mode=DataMode.HISTORICAL, provider="fixture", nodes=[GraphNode(id=x, address=x, depth=i) for i, x in enumerate([ROOT, OTHER, EXCHANGE])], edges=[late_reverse, terminal, first], signals=[], evidence=[])
    primary = select_primary_path(trace, entities, sources, [item for item in records if item.entity_id == "entity-a"])
    assert primary["transaction_hashes"] == [first.transaction_hash, terminal.transaction_hash]
    assert primary["edge_ids"] == [first.edge_id, terminal.edge_id]
    assert primary["transaction_count"] == 2
    assert primary["total_transferred_value"] == "0.75 ETH + 1.16 USDT"
    assert primary["path_duration_seconds"] == 86400.0

def test_development_registry_resolves_synthetic_terminal_only():
    entities, sources, records = merge_synthetic_attribution([], [], [])
    e1 = edge("1", ROOT, OTHER)
    e2 = edge("2", OTHER, DEMO_VASP_ADDRESS)
    trace = TraceResult(case_id="case", trace_id="trace", root_address=ROOT, mode=DataMode.HISTORICAL, provider="DEVELOPMENT SYNTHETIC", nodes=[GraphNode(id=x, address=x, depth=i) for i, x in enumerate([ROOT, OTHER, DEMO_VASP_ADDRESS])], edges=[e1, e2], signals=[], evidence=[])
    primary = select_primary_path(trace, entities, sources, records)
    assert primary["status"] == "ATTRIBUTED"
    assert primary["terminal_entity_name"] == "Demo Exchange"
    assert primary["terminal_entity_type"] == "VASP"
    assert primary["attribution"] == "HIGH"
    assert primary["terminal_address"] == DEMO_VASP_ADDRESS
