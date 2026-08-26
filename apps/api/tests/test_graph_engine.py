from datetime import datetime, timezone, timedelta
import pytest
from app.domain import Chain, TraceDirection, TraceRequest, Transfer
from app.graph_engine import GraphAnalyzer, GraphBuilder
from app.provider import BlockchainProvider
from app.services import TraceService

def transfer(tx, source, target, asset="ETH", amount="1", offset=0, transfer_type="native"):
    return Transfer(tx_hash="0x"+tx*64,chain=Chain.ETHEREUM,source="0x"+source*40,destination="0x"+target*40,asset=asset,amount=amount,value_native=float(amount) if transfer_type=="native" else None,provider="fixture",timestamp=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=offset),transfer_type=transfer_type)

def test_multigraph_preserves_repeated_transactions_and_assets():
    _,nodes,edges=GraphBuilder().build([transfer("1","a","b"),transfer("2","a","b","USDT","500",1,"token"),transfer("3","a","b")],"0x"+"a"*40)
    assert len(nodes)==2 and len(edges)==3

def test_metrics_and_shortest_paths_are_observational():
    graph,nodes,edges=GraphBuilder().build([transfer("1","a","b"),transfer("2","b","c")],"0x"+"a"*40)
    analyzer=GraphAnalyzer(); paths=analyzer.paths(graph,"0x"+"a"*40)
    assert paths and paths[0].node_ids==["0x"+"a"*40,"0x"+"b"*40]
    metrics=analyzer.metrics(graph,nodes,edges,"0x"+"a"*40,paths)
    assert metrics.node_count==3 and metrics.edge_count==2 and metrics.unique_transaction_count==2

class FixtureProvider(BlockchainProvider):
    name="fixture"
    async def get_address_transfers(self,address,chain,**kwargs):
        a=address.lower()
        rows={
            "0x"+"a"*40:[transfer("1","a","b"),transfer("2","a","b","USDT","500",1,"token")],
            "0x"+"b"*40:[transfer("3","b","c",offset=2)],
            "0x"+"c"*40:[transfer("4","a","c",offset=3),transfer("5","b","c",offset=3)],
        }
        return rows.get(a,[])
    async def get_transaction(self,*args): return None
    async def get_transaction_receipt(self,*args): return None
    async def get_block(self,*args): return None
    def capabilities(self): return []

@pytest.mark.asyncio
async def test_trace_supports_forward_backward_filters_and_partial_limits():
    service=TraceService(FixtureProvider()); root="0x"+"a"*40
    forward=await service.trace("case",TraceRequest(address=root,direction=TraceDirection.FORWARD,max_hops=2,max_nodes=10,asset_filter="ETH"))
    assert len(forward.edges)==2 and forward.status=="COMPLETED"
    backward=await service.trace("case",TraceRequest(address="0x"+"c"*40,direction=TraceDirection.BACKWARD,max_hops=2,max_nodes=10))
    assert len(backward.edges)==2
    partial=await service.trace("case",TraceRequest(address=root,max_hops=4,max_nodes=2,max_edges=10))
    assert partial.status=="PARTIAL"
