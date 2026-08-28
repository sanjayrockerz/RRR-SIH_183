import pytest
from app.domain import CapabilityStatus, Chain, DataMode, ProviderCapability
from app.provider import BlockchainProvider, ProviderError
from app.provider_registry import BlockchainProviderRegistry


class FixtureProvider(BlockchainProvider):
    name = "Fixture"

    def __init__(self, status=CapabilityStatus.SUPPORTED):
        self.status = status

    def capabilities(self):
        return [ProviderCapability(name="address_transactions", status=self.status, mode=DataMode.HISTORICAL, note="Test capability")]

    async def get_address_transfers(self, address, chain, **kwargs): return []
    async def get_transaction(self, tx_hash, chain): return None
    async def get_transaction_receipt(self, tx_hash, chain): return None
    async def get_block(self, block_number, chain): return None


def test_registry_selects_provider_by_chain_and_exposes_capability_state():
    registry = BlockchainProviderRegistry([([Chain.ETHEREUM], FixtureProvider())])
    assert registry.get(Chain.ETHEREUM).name == "Fixture"
    status = registry.statuses()[0]
    assert status.status == CapabilityStatus.SUPPORTED
    assert status.capabilities[0].name == "address_transactions"
    assert "secret" not in status.detail.lower()


def test_unconfigured_provider_is_not_used_for_ingestion():
    registry = BlockchainProviderRegistry([([Chain.TRON], FixtureProvider(CapabilityStatus.NOT_CONFIGURED))])
    with pytest.raises(ProviderError, match="not configured"):
        registry.get(Chain.TRON)


def test_duplicate_chain_registration_is_rejected():
    with pytest.raises(ValueError, match="Multiple blockchain providers"):
        BlockchainProviderRegistry([([Chain.ETHEREUM], FixtureProvider()), ([Chain.ETHEREUM], FixtureProvider())])


def test_missing_chain_is_explicit_provider_error():
    registry = BlockchainProviderRegistry([])
    with pytest.raises(ProviderError, match="No blockchain provider"):
        registry.get(Chain.TRON)
