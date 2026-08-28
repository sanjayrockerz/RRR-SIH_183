import hashlib
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

def derive_address(base_addr: str, salt: str) -> str:
    h = hashlib.md5((base_addr.lower() + salt).encode('utf-8')).hexdigest()
    return "0x" + h + "0" * (40 - len(h))

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
        
        # 1. If it's a known fixture wallet, return the static list filters
        known_wallets = {FIXTURE_WALLETS[k].lower() for k in ("a","b","c","d","e","dex")}
        if normalized in known_wallets:
            return [item for item in self._transfers() if item.source.lower() == normalized or item.destination.lower() == normalized][:max_transactions]
            
        # 2. Otherwise, dynamically generate a deterministic flow graph centered on this custom wallet
        # We need to return transfers for the base address as well as its derived child addresses so BFS traversal finds them.
        # Let's derive seed from address
        try:
            seed_val = int(normalized[2:10], 16)
        except Exception:
            seed_val = 123456

        # Let's define the nodes in our custom sub-graph
        base = normalized
        child1 = derive_address(base, "child1")
        child2 = derive_address(base, "child2")
        mixer = derive_address(base, "mixer")
        bridge = derive_address(base, "bridge")
        vasp = derive_address(base, "vasp")

        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        def make_tx(n, src, dest, amt, asset="ETH", kind="native", mins=5):
            tx_h = "0x" + hashlib.sha256(f"{base}:{n}".encode()).hexdigest()
            return Transfer(
                tx_hash=tx_h,
                chain=Chain.ETHEREUM,
                block_number=21000000+n,
                timestamp=t0+timedelta(minutes=mins),
                source=src,
                destination=dest,
                asset=asset,
                amount=str(amt),
                value_native=float(amt) if kind == "native" else None,
                provider=self.name,
                transfer_type=kind,
                contract_address=None,
                raw_reference={"fixture_id": seed_val + n, "source_mode": "DEVELOPMENT_FIXTURE"}
            )

        # Generate custom flow structures
        all_generated = []
        if seed_val % 3 == 0:
            # High Risk Route (base -> child1 -> child2 -> mixer / vasp)
            all_generated = [
                make_tx(1, base, child1, 10.0, mins=1),
                make_tx(2, child1, child2, 9.9, mins=2),
                make_tx(3, child2, mixer, 9.8, mins=3),
                make_tx(4, child2, vasp, 0.1, mins=4),
            ]
        elif seed_val % 3 == 1:
            # Medium Risk Route (base -> child1 -> bridge)
            all_generated = [
                make_tx(1, base, child1, 5.0, mins=5),
                make_tx(2, child1, bridge, 4.8, mins=10),
            ]
        else:
            # Low Risk Route (base -> child1 -> child2)
            all_generated = [
                make_tx(1, base, child1, 1.2, mins=20),
                make_tx(2, child1, child2, 1.1, mins=40),
            ]

        # Filter the generated transfers that contain the requested address as source or destination
        return [tx for tx in all_generated if tx.source.lower() == normalized or tx.destination.lower() == normalized][:max_transactions]

    async def get_transaction(self, tx_hash, chain): return None
    async def get_transaction_receipt(self, tx_hash, chain): return None
    async def get_block(self, block_number, chain): return None
