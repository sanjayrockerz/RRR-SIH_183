from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain import Chain, DataMode, Evidence, GraphEdge, GraphNode, RealtimeEvent, TraceResult, Transfer
from app.config import settings
from app.graph.neo4j_client import Neo4jClient
from app.graph.neo4j_repository import deterministic_id
from app.graph.graph_projection import GraphProjectionService


def test_relationship_ids_are_deterministic_and_order_sensitive():
    assert deterministic_id("edge", "ethereum", "tx") == deterministic_id("edge", "ethereum", "tx")
    assert deterministic_id("edge", "ethereum", "tx") != deterministic_id("edge", "tron", "tx")


@pytest.mark.asyncio
async def test_projection_is_explicitly_not_configured_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "neo4j_uri", "")
    monkeypatch.setattr(settings, "neo4j_password", "")
    client = Neo4jClient()
    await client.connect()
    service = GraphProjectionService(client)
    assert service.status().status.value == "NOT_CONFIGURED"
    assert await service.project(TraceResult(case_id=str(uuid4()),root_address="0x"+"a"*40,mode=DataMode.HISTORICAL,provider="fixture",nodes=[],edges=[],signals=[],evidence=[])) == 0
    event=RealtimeEvent(event_id="event-1",provider="fixture",chain=Chain.ETHEREUM,received_at=datetime.now(timezone.utc),transaction_hash="0x"+"1"*64,from_address="0x"+"a"*40,to_address="0x"+"b"*40,asset="ETH",amount="1")
    assert await service.project_incremental(str(uuid4()),event) == 0


def test_projection_domain_fixture_preserves_evidence_fields():
    now=datetime.now(timezone.utc)
    tx=Transfer(tx_hash="0x"+"1"*64,chain=Chain.ETHEREUM,source="0x"+"a"*40,destination="0x"+"b"*40,asset="ETH",amount="1",provider="fixture",timestamp=now)
    result=TraceResult(case_id=str(uuid4()),root_address=tx.source,mode=DataMode.HISTORICAL,provider="fixture",nodes=[GraphNode(id=tx.source,address=tx.source),GraphNode(id=tx.destination,address=tx.destination)],edges=[GraphEdge(source=tx.source,target=tx.destination,transfer=tx,evidence_id="evidence-1")],signals=[],evidence=[Evidence(evidence_id="evidence-1",case_id="case",type="TRANSACTION",chain=Chain.ETHEREUM,tx_hash=tx.tx_hash,source="fixture",captured_at=now)])
    assert result.edges[0].transfer.tx_hash == result.evidence[0].tx_hash
