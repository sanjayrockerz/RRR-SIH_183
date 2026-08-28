from datetime import datetime, timedelta, timezone
from .data_fabric import BlockchainDataFabric
from .domain import BlockHeader, Chain, ProviderCapability, CapabilityStatus, DataMode, TransactionDetails, TransactionReceipt, Transfer

FIXTURE_WALLETS = {
    "a": "0x1111111111111111111111111111111111111111",
    "b": "0x2222222222222222222222222222222222222222",
    "c": "0x3333333333333333333333333333333333333333",
    "d": "0x4444444444444444444444444444444444444444",
    "e": "0x5555555555555555555555555555555555555555",
    "dex": "0x9999999999999999999999999999999999999999",
}

class DevelopmentFixtureProvider(BlockchainDataFabric):
    """Deterministic, explicitly labelled provider for local end-to-end verification."""
    name = "Development Fixture"

    def capabilities(self):
        return [ProviderCapability(name="fixture_blockchain_data", status=CapabilityStatus.SIMULATED, mode=DataMode.DEVELOPMENT_FIXTURE, note="Deterministic local dataset; never represents live chain state.")]

    def _transfers(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        def tx(n, source, destination, asset="ETH", amount="1", kind="native", contract=None, minutes=0):
            return Transfer(tx_hash="0x" + f"{n:064x}", chain=Chain.ETHEREUM, block_number=21000000+n, timestamp=t0+timedelta(minutes=minutes), source=source, destination=destination, asset=asset, amount=amount, value_native=float(amount) if kind == "native" else None, provider=self.name, transfer_type=kind, contract_address=contract, raw_reference={"fixture_id": n, "source_mode": "DEVELOPMENT_FIXTURE"})
        a,b,c,d,e,x = (FIXTURE_WALLETS[k] for k in ("a","b","c","d","e","dex"))
        return [tx(1,a,b,amount="10",minutes=1), tx(2,b,c,amount="8",minutes=3), tx(3,c,d,amount="7",minutes=5), tx(4,a,c,amount="2",minutes=2), tx(5,a,d,amount="1",minutes=2), tx(6,d,e,amount="6",minutes=7), tx(7,c,x,asset="USDC",amount="100",kind="erc20",contract="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",minutes=6), tx(8,x,d,asset="USDC",amount="95",kind="erc20",contract="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",minutes=8)]

    async def get_address_transfers(self, address, chain, *, page_size=100, max_pages=10, max_transactions=500):
        if chain != Chain.ETHEREUM: return []
        normalized = address.lower()
        return [item for item in self._transfers() if item.source.lower() == normalized or item.destination.lower() == normalized][:max_transactions]

    async def get_transaction(self, tx_hash, chain): return None
    async def get_transaction_receipt(self, tx_hash, chain): return None
    async def get_block(self, block_number, chain): return None
