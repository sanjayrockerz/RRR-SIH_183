import time
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any
import asyncio
import httpx
from .config import settings
from .data_fabric import BlockchainDataFabric
from .domain import (
    BlockHeader, CapabilityStatus, Chain, DataMode, ProviderCapability,
    TransactionDetails, TransactionReceipt, Transfer,
)

class ProviderError(RuntimeError):
    """A provider failure safe to surface at the application boundary."""

class BlockchainProvider(BlockchainDataFabric):
    name = "unknown"

    def capabilities(self) -> list[ProviderCapability]:
        raise NotImplementedError

class AlchemyEthereumProvider(BlockchainProvider):
    name = "Alchemy Ethereum"

    def capabilities(self):
        status = CapabilityStatus.SUPPORTED if settings.alchemy_api_key else CapabilityStatus.NOT_CONFIGURED
        return [
            ProviderCapability(name="address_transactions", status=status, mode=DataMode.HISTORICAL, note="Alchemy alchemy_getAssetTransfers with pageKey pagination and bounded limits."),
            ProviderCapability(name="transaction", status=status, mode=DataMode.HISTORICAL, note="eth_getTransactionByHash with raw provider reference."),
            ProviderCapability(name="transaction_receipt", status=status, mode=DataMode.HISTORICAL, note="eth_getTransactionReceipt with gas/status fields."),
            ProviderCapability(name="block", status=status, mode=DataMode.HISTORICAL, note="eth_getBlockByNumber with timestamp and hash."),
            ProviderCapability(name="token_transfers", status=status, mode=DataMode.HISTORICAL, note="Returned as normalized transfer rows from alchemy_getAssetTransfers."),
            ProviderCapability(name="websocket_subscription", status=CapabilityStatus.UNSUPPORTED, mode=DataMode.SUBSCRIPTION, note="Alchemy WebSocket event adapter is not enabled."),
            ProviderCapability(name="webhook_events", status=CapabilityStatus.SUPPORTED if (settings.alchemy_api_key and settings.alchemy_webhook_id and settings.alchemy_webhook_signing_key) else CapabilityStatus.NOT_CONFIGURED, mode=DataMode.WEBHOOK, note="Alchemy Notify Address Activity webhook ingestion endpoint."),
            ProviderCapability(name="incremental_retracing", status=CapabilityStatus.SUPPORTED if (settings.alchemy_api_key and settings.alchemy_webhook_id and settings.alchemy_webhook_signing_key) else CapabilityStatus.NOT_CONFIGURED, mode=DataMode.WEBHOOK, note="Incremental graph, pattern, and risk processing after webhook configuration."),
            ProviderCapability(name="realtime_alerts", status=CapabilityStatus.SUPPORTED if (settings.alchemy_api_key and settings.alchemy_webhook_id and settings.alchemy_webhook_signing_key) else CapabilityStatus.NOT_CONFIGURED, mode=DataMode.WEBHOOK, note="Evidence-backed internal investigative alert candidates."),
        ]

    async def health(self):
        if not settings.alchemy_api_key:
            return {
                "provider": "alchemy",
                "network": settings.alchemy_network,
                "configured": False,
                "reachable": False,
                "status": "NOT_CONFIGURED",
                "latency_ms": 0,
                "last_checked": datetime.now(timezone.utc).isoformat(),
                "capabilities": ["historical_transfers", "transaction_lookup", "receipt_lookup", "token_transfers"],
                "detail": "ALCHEMY_API_KEY is not configured"
            }
        t0 = time.monotonic()
        try:
            result = await self._rpc("eth_blockNumber", [])
            latency_ms = int((time.monotonic() - t0) * 1000)
            return {
                "provider": "alchemy",
                "network": settings.alchemy_network,
                "configured": True,
                "reachable": True,
                "status": "CONNECTED",
                "latency_ms": latency_ms,
                "last_checked": datetime.now(timezone.utc).isoformat(),
                "capabilities": ["historical_transfers", "transaction_lookup", "receipt_lookup", "token_transfers"],
                "detail": f"Alchemy RPC probe succeeded, latest block: {result}"
            }
        except ProviderError as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            return {
                "provider": "alchemy",
                "network": settings.alchemy_network,
                "configured": True,
                "reachable": False,
                "status": "DEGRADED",
                "latency_ms": latency_ms,
                "last_checked": datetime.now(timezone.utc).isoformat(),
                "capabilities": ["historical_transfers", "transaction_lookup", "receipt_lookup", "token_transfers"],
                "detail": f"Alchemy connection degraded: {str(exc)}"
            }

    def _url(self):
        if not settings.alchemy_api_key:
            raise ProviderError("ALCHEMY_API_KEY is not configured")
        base = settings.alchemy_base_url or f"https://{settings.alchemy_network}.g.alchemy.com/v2"
        return f"{base.rstrip('/')}/{settings.alchemy_api_key}"

    async def _rpc(self, method: str, params: list[Any]) -> dict:
        attempts=max(1,settings.provider_max_retries+1)
        try:
            async with httpx.AsyncClient(timeout=settings.alchemy_timeout_seconds) as client:
                for attempt in range(attempts):
                    try:
                        response = await client.post(self._url(), json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt+1 < attempts:
                                await asyncio.sleep(min(2 ** attempt, 4)); continue
                        response.raise_for_status(); data = response.json(); break
                    except (httpx.TimeoutException, httpx.NetworkError):
                        if attempt+1 >= attempts: raise
                        await asyncio.sleep(min(2 ** attempt, 4))
                else: raise ProviderError(f"Alchemy {method} request exhausted retries")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Alchemy {method} request failed") from exc
        if not isinstance(data, dict) or "error" in data:
            raise ProviderError(f"Alchemy {method} returned an error")
        return data.get("result") or {}

    async def get_address_transfers(self, address: str, chain: Chain, *, page_size: int = 100,
                                    max_pages: int = 10, max_transactions: int = 500) -> list[Transfer]:
        if chain != Chain.ETHEREUM:
            raise ProviderError("Alchemy Ethereum provider does not support this chain")
        page_size = max(1, min(page_size, 1000)); max_pages = max(1, max_pages); max_transactions = max(1, max_transactions)
        transfers: list[Transfer] = []
        for direction in ("from", "to"):
            page_key = None
            for page_number in range(max_pages):
                params = {
                    "fromBlock": "0x0", "toBlock": "latest", direction: address,
                    "category": ["external", "erc20", "erc721", "erc1155"],
                    "withMetadata": True, "maxCount": hex(page_size),
                }
                if page_key:
                    params["pageKey"] = page_key
                result = await self._rpc("alchemy_getAssetTransfers", [params])
                items = result.get("transfers", [])
                if not isinstance(items, list):
                    raise ProviderError("Alchemy returned malformed transfer data")
                for item in items:
                    transfers.append(self._normalize_transfer(item, chain))
                    if len(transfers) >= max_transactions:
                        return self._deduplicate(transfers)[:max_transactions]
                next_page_key = result.get("pageKey")
                if not next_page_key or not items or next_page_key == page_key:
                    break
                page_key = next_page_key
        return self._deduplicate(transfers)[:max_transactions]

    def _normalize_transfer(self, item: dict, chain: Chain) -> Transfer:
        try:
            metadata = item.get("metadata") or {}
            timestamp = metadata.get("blockTimestamp")
            asset = item.get("asset") or "ETH"
            transfer_type = "native" if asset == "ETH" and not item.get("rawContract", {}).get("address") else "token"
            raw_contract = item.get("rawContract") or {}
            raw_reference = {
                "provider": self.name, "method": "alchemy_getAssetTransfers",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "provider_hash": item.get("hash"), "payload": item,
            }
            return Transfer(
                tx_hash=item["hash"], chain=chain,
                block_number=int(item["blockNum"], 16) if item.get("blockNum") else None,
                timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else None,
                source=item.get("from", ""), destination=item.get("to", ""),
                asset=asset, amount=str(item.get("value") or "0"),
                value_native=float(item["value"]) if item.get("value") is not None else None,
                provider=self.name, transfer_type=transfer_type,
                contract_address=raw_contract.get("address"),
                token_id=str(item["tokenId"]) if item.get("tokenId") is not None else None,
                decimals=self._parse_int(raw_contract["decimal"]) if raw_contract.get("decimal") is not None else None,
                raw_reference=raw_reference,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Alchemy returned malformed transfer data") from exc

    @staticmethod
    def _parse_int(value: Any) -> int:
        return int(value, 0) if isinstance(value, str) else int(value)

    async def get_transaction(self, tx_hash: str, chain: Chain) -> TransactionDetails | None:
        if chain != Chain.ETHEREUM: raise ProviderError("Alchemy Ethereum provider does not support this chain")
        result = await self._rpc("eth_getTransactionByHash", [tx_hash])
        if not result:
            return None
        return TransactionDetails(
            tx_hash=tx_hash, chain=chain, block_number=int(result["blockNumber"], 16) if result.get("blockNumber") else None,
            status="MINED" if result.get("blockNumber") else "PENDING", from_address=result.get("from", ""),
            to_address=result.get("to") or "", native_value=str(int(result.get("value", "0x0"), 16)),
            nonce=int(result["nonce"], 16) if result.get("nonce") else None,
            gas_limit=int(result["gas"], 16) if result.get("gas") else None,
            gas_price=str(int(result["gasPrice"], 16)) if result.get("gasPrice") else None,
            raw_reference={"provider": self.name, "method": "eth_getTransactionByHash", "retrieved_at": datetime.now(timezone.utc).isoformat(), "payload": result},
        )

    async def get_transaction_receipt(self, tx_hash: str, chain: Chain) -> TransactionReceipt | None:
        if chain != Chain.ETHEREUM: raise ProviderError("Alchemy Ethereum provider does not support this chain")
        result = await self._rpc("eth_getTransactionReceipt", [tx_hash])
        if not result:
            return None
        status = "SUCCESS" if result.get("status") == "0x1" else "FAILED" if result.get("status") == "0x0" else "UNKNOWN"
        return TransactionReceipt(tx_hash=tx_hash, chain=chain, status=status, block_number=int(result["blockNumber"], 16) if result.get("blockNumber") else None, gas_used=int(result["gasUsed"], 16) if result.get("gasUsed") else None, effective_gas_price=str(int(result["effectiveGasPrice"], 16)) if result.get("effectiveGasPrice") else None, raw_reference={"provider": self.name, "method": "eth_getTransactionReceipt", "retrieved_at": datetime.now(timezone.utc).isoformat(), "payload": result})

    async def get_block(self, block_number: int, chain: Chain) -> BlockHeader | None:
        if chain != Chain.ETHEREUM: raise ProviderError("Alchemy Ethereum provider does not support this chain")
        result = await self._rpc("eth_getBlockByNumber", [hex(block_number), False])
        if not result:
            return None
        return BlockHeader(chain=chain, block_number=int(result["number"], 16), block_hash=result.get("hash"), timestamp=datetime.fromtimestamp(int(result["timestamp"], 16), tz=timezone.utc) if result.get("timestamp") else None, parent_hash=result.get("parentHash"), raw_reference={"provider": self.name, "method": "eth_getBlockByNumber", "retrieved_at": datetime.now(timezone.utc).isoformat(), "payload": result})

    @staticmethod
    def _deduplicate(transfers: list[Transfer]) -> list[Transfer]:
        seen: set[tuple[str, Chain, str, str, str]] = set(); result = []
        for transfer in transfers:
            key=(transfer.tx_hash, transfer.chain, transfer.source.lower(), transfer.destination.lower(), transfer.asset)
            if key not in seen:
                seen.add(key); result.append(transfer)
        return result


class TronGridProvider(BlockchainProvider):
    """Bounded TronGrid adapter. No API key means NOT_CONFIGURED, never simulated."""
    name = "TronGrid"

    def configured(self): return bool(settings.trongrid_api_key)
    def capabilities(self):
        status=CapabilityStatus.SUPPORTED if self.configured() else CapabilityStatus.NOT_CONFIGURED
        return [
            ProviderCapability(name="address_transactions",status=status,mode=DataMode.HISTORICAL,note="TronGrid account transaction and TRC20 endpoints with bounded pagination."),
            ProviderCapability(name="transaction",status=status,mode=DataMode.HISTORICAL,note="TronGrid transaction detail endpoint."),
            ProviderCapability(name="transaction_receipt",status=status,mode=DataMode.HISTORICAL,note="TronGrid transaction info endpoint."),
            ProviderCapability(name="block",status=status,mode=DataMode.HISTORICAL,note="TronGrid block endpoint."),
            ProviderCapability(name="token_transfers",status=status,mode=DataMode.HISTORICAL,note="TRC20 account transfer endpoint."),
            ProviderCapability(name="webhook_events",status=CapabilityStatus.NOT_CONFIGURED,mode=DataMode.WEBHOOK,note="No Tron realtime adapter is enabled."),
        ]

    async def health(self):
        if not self.configured():
            return {"status": "NOT_CONFIGURED", "detail": "TRONGRID_API_KEY is not configured"}
        try:
            await self._request("/wallet/getnowblock", {}, post=True)
            return {"status": "CONNECTED", "detail": "TronGrid probe succeeded"}
        except ProviderError as exc:
            return {"status": "DEGRADED", "detail": str(exc)}

    def _url(self, path):
        if not self.configured(): raise ProviderError("TRONGRID_API_KEY is not configured")
        return settings.trongrid_base_url.rstrip("/")+path

    async def _request(self,path,params=None,post=False):
        attempts=max(1,settings.provider_max_retries+1)
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                headers={"TRON-PRO-API-KEY":settings.trongrid_api_key}
                for attempt in range(attempts):
                    try:
                        response=await (client.post(self._url(path),json=params or {},headers=headers) if post else client.get(self._url(path),params=params or {},headers=headers))
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt+1 < attempts:
                                await asyncio.sleep(min(2 ** attempt, 4)); continue
                        response.raise_for_status(); payload=response.json(); break
                    except (httpx.TimeoutException, httpx.NetworkError):
                        if attempt+1 >= attempts: raise
                        await asyncio.sleep(min(2 ** attempt, 4))
                else: raise ProviderError(f"TronGrid request exhausted retries for {path}")
        except (httpx.HTTPError,ValueError) as exc: raise ProviderError(f"TronGrid request failed for {path}") from exc
        if not isinstance(payload,dict) or payload.get("success") is False: raise ProviderError(f"TronGrid returned an error for {path}")
        return payload

    async def get_address_transfers(self,address,chain:Chain,*,page_size=100,max_pages=10,max_transactions=500):
        if chain != Chain.TRON: raise ProviderError("TronGrid provider does not support this chain")
        result=[]; fingerprint=None
        for _ in range(max(1,max_pages)):
            params={"limit":min(max(1,page_size),200),"only_confirmed":"true","order_by":"block_timestamp,asc"}
            if fingerprint: params["fingerprint"]=fingerprint
            payload=await self._request(f"/v1/accounts/{address}/transactions/trc20",params)
            rows=payload.get("data",[])
            if not isinstance(rows,list): raise ProviderError("TronGrid returned malformed TRC20 data")
            for row in rows:
                token=row.get("token_info") or {}; timestamp=(row.get("block_timestamp") or 0)/1000 if row.get("block_timestamp") else None
                result.append(Transfer(tx_hash=row["transaction_id"],chain=Chain.TRON,block_number=None,timestamp=datetime.fromtimestamp(timestamp,tz=timezone.utc) if timestamp else None,source=row.get("from", ""),destination=row.get("to", ""),asset=token.get("symbol") or token.get("address") or "TRC20",amount=str(row.get("value") or "0"),provider=self.name,transfer_type="token",contract_address=token.get("address"),decimals=int(token["decimals"]) if token.get("decimals") is not None else None,raw_reference={"provider":self.name,"method":"/v1/accounts/{address}/transactions/trc20","retrieved_at":datetime.now(timezone.utc).isoformat(),"payload":row}))
                if len(result)>=max_transactions: return self._deduplicate(result)[:max_transactions]
            fingerprint=(payload.get("meta") or {}).get("fingerprint")
            if not fingerprint or not rows: break
        return self._deduplicate(result)[:max_transactions]

    async def get_transaction(self,tx_hash,chain):
        if chain != Chain.TRON: raise ProviderError("TronGrid provider does not support this chain")
        payload=await self._request("/wallet/gettransactionbyid",{"value":tx_hash},post=True)
        if not payload: return None
        block=payload.get("blockNumber"); return TransactionDetails(tx_hash=tx_hash,chain=chain,block_number=block,status="MINED" if block else "UNKNOWN",raw_reference={"provider":self.name,"method":"/wallet/gettransactionbyid","payload":payload})

    async def get_transaction_receipt(self,tx_hash,chain):
        if chain != Chain.TRON: raise ProviderError("TronGrid provider does not support this chain")
        payload=await self._request("/wallet/gettransactioninfobyid",{"value":tx_hash},post=True)
        if not payload: return None
        result=payload.get("receipt") or {}; status="SUCCESS" if result.get("result")=="SUCCESS" else "FAILED" if result else "UNKNOWN"
        return TransactionReceipt(tx_hash=tx_hash,chain=chain,status=status,block_number=payload.get("blockNumber"),raw_reference={"provider":self.name,"method":"/wallet/gettransactioninfobyid","payload":payload})

    async def get_block(self,block_number,chain):
        if chain != Chain.TRON: raise ProviderError("TronGrid provider does not support this chain")
        payload=await self._request("/wallet/getblockbynum",{"num":block_number},post=True)
        if not payload: return None
        return BlockHeader(chain=chain,block_number=block_number,block_hash=payload.get("blockID"),timestamp=datetime.fromtimestamp(payload["block_header"]["raw_data"]["timestamp"]/1000,tz=timezone.utc) if payload.get("block_header",{}).get("raw_data",{}).get("timestamp") else None,raw_reference={"provider":self.name,"method":"/wallet/getblockbynum","payload":payload})

    @staticmethod
    def _deduplicate(transfers):
        seen=set(); result=[]
        for item in transfers:
            key=(item.chain,item.tx_hash,item.source.lower(),item.destination.lower(),item.asset,item.amount)
            if key not in seen: seen.add(key); result.append(item)
        return result
