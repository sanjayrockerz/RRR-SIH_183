from datetime import datetime, timezone
from .domain import CapabilityStatus, Chain, ProviderOperationalStatus
from .provider import BlockchainProvider, ProviderError


class BlockchainProviderRegistry:
    """Selects a configured blockchain adapter by chain without leaking vendor names into services."""

    def __init__(self, providers: list[tuple[list[Chain], BlockchainProvider]]):
        self._by_chain: dict[Chain, BlockchainProvider] = {}
        self._providers: list[tuple[list[Chain], BlockchainProvider]] = []
        for chains, provider in providers:
            self._providers.append((chains, provider))
            for chain in chains:
                if chain in self._by_chain:
                    raise ValueError(f"Multiple blockchain providers registered for {chain}")
                self._by_chain[chain] = provider

    def get(self, chain: Chain) -> BlockchainProvider:
        provider=self._by_chain.get(chain)
        if not provider:
            raise ProviderError(f"No blockchain provider registered for {chain}")
        statuses=[item.status for item in provider.capabilities()]
        if statuses and all(status == CapabilityStatus.NOT_CONFIGURED for status in statuses):
            raise ProviderError(f"Blockchain provider for {chain} is not configured")
        return provider

    def statuses(self) -> list[ProviderOperationalStatus]:
        now=datetime.now(timezone.utc); result=[]
        for chains, provider in self._providers:
            capabilities=provider.capabilities(); statuses=[item.status for item in capabilities]
            if any(status == CapabilityStatus.SUPPORTED for status in statuses): status=CapabilityStatus.SUPPORTED
            elif any(status == CapabilityStatus.UNAVAILABLE for status in statuses): status=CapabilityStatus.UNAVAILABLE
            else: status=CapabilityStatus.NOT_CONFIGURED
            result.append(ProviderOperationalStatus(provider=provider.name,chains=chains,status=status,capabilities=capabilities,checked_at=now,detail="Configuration/capability status only; no network request was made."))
        return result
