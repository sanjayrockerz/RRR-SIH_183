from datetime import datetime, timezone
from app.attribution import AttributionEngine, NearestEntityResolver
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
