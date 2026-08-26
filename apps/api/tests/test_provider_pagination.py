from app.provider import AlchemyEthereumProvider
from app.domain import Chain, Transfer
import pytest

def test_provider_deduplicates_same_chain_transaction():
    tx="0x"+"1"*64
    transfers=[Transfer(tx_hash=tx,chain=Chain.ETHEREUM,source="0x"+"a"*40,destination="0x"+"b"*40,asset="ETH",amount="1",provider="fixture"), Transfer(tx_hash=tx,chain=Chain.ETHEREUM,source="0x"+"a"*40,destination="0x"+"b"*40,asset="ETH",amount="1",provider="fixture")]
    assert len(AlchemyEthereumProvider._deduplicate(transfers)) == 1

def test_alchemy_normalizes_token_metadata_and_raw_reference():
    item={"hash":"0x"+"2"*64,"blockNum":"0x10","from":"0x"+"a"*40,"to":"0x"+"b"*40,"asset":"USDC","value":12.5,"rawContract":{"address":"0x"+"c"*40,"decimal":"0x6"},"metadata":{"blockTimestamp":"2025-01-01T00:00:00Z"}}
    transfer=AlchemyEthereumProvider()._normalize_transfer(item,Chain.ETHEREUM)
    assert transfer.transfer_type=="token"
    assert transfer.contract_address=="0x"+"c"*40
    assert transfer.decimals==6
    assert transfer.raw_reference["method"]=="alchemy_getAssetTransfers"
    assert transfer.raw_reference["payload"]["hash"]==item["hash"]

@pytest.mark.asyncio
async def test_alchemy_follows_cursor_and_stops_at_bound():
    provider=AlchemyEthereumProvider()
    a="0x"+"a"*40; b="0x"+"b"*40
    item=lambda n: {"hash":"0x"+str(n)*64,"blockNum":"0x10","from":a,"to":b,"asset":"ETH","value":1}
    calls=[]
    async def fake_rpc(method,params):
        calls.append(params[0])
        if len(calls)==1: return {"transfers":[item(1)],"pageKey":"next"}
        if len(calls)==2: return {"transfers":[item(2)]}
        return {"transfers":[item(1)]}
    provider._rpc=fake_rpc
    result=await provider.get_address_transfers(a,Chain.ETHEREUM,page_size=1,max_pages=4,max_transactions=2)
    assert len(result)==2
    assert calls[1]["pageKey"]=="next"

@pytest.mark.asyncio
async def test_alchemy_normalizes_transaction_receipt_and_block():
    provider=AlchemyEthereumProvider()
    async def fake_rpc(method,params):
        if method=="eth_getTransactionByHash":
            return {"hash":params[0],"blockNumber":"0x10","from":"0x"+"a"*40,"to":"0x"+"b"*40,"value":"0xde0b6b3a7640000","nonce":"0x2","gas":"0x5208","gasPrice":"0x3b9aca00"}
        if method=="eth_getTransactionReceipt":
            return {"transactionHash":params[0],"blockNumber":"0x10","status":"0x1","gasUsed":"0x5208","effectiveGasPrice":"0x3b9aca00"}
        return {"number":"0x10","hash":"0x"+"3"*64,"timestamp":"0x67748580","parentHash":"0x"+"4"*64}
    provider._rpc=fake_rpc
    tx=await provider.get_transaction("0x"+"1"*64,Chain.ETHEREUM)
    receipt=await provider.get_transaction_receipt(tx.tx_hash,Chain.ETHEREUM)
    block=await provider.get_block(16,Chain.ETHEREUM)
    assert tx.native_value=="1000000000000000000" and tx.gas_limit==21000
    assert receipt.status=="SUCCESS" and receipt.gas_used==21000
    assert block.block_number==16 and block.raw_reference["method"]=="eth_getBlockByNumber"
