import pytest
from app.domain import Chain, Transfer, TraceRequest
from app.provider import BlockchainProvider
from app.services import TraceService
class FakeProvider(BlockchainProvider):
    name="Fixture provider"
    def capabilities(self): return []
    async def get_transaction(self,tx_hash,chain): return None
    async def get_transaction_receipt(self,tx_hash,chain): return None
    async def get_block(self,block_number,chain): return None
    async def get_address_transfers(self,address,chain,**kwargs):
        a=address.lower(); rows={"0x"+"a"*40:[Transfer(tx_hash="0x"+"1"*64,chain=chain,source="0x"+"a"*40,destination="0x"+"b"*40,asset="ETH",amount="1",value_native=1,provider=self.name)],"0x"+"b"*40:[Transfer(tx_hash="0x"+"2"*64,chain=chain,source="0x"+"b"*40,destination="0x"+"c"*40,asset="ETH",amount="0.5",value_native=.5,provider=self.name)]}; return rows.get(a,[])
@pytest.mark.asyncio
async def test_bounded_trace_preserves_edges():
    result=await TraceService(FakeProvider()).trace("case",TraceRequest(address="0x"+"a"*40,max_hops=2,max_nodes=10))
    assert len(result.nodes)==3 and len(result.edges)==2 and len(result.evidence)==2
