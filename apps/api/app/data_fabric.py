from abc import ABC, abstractmethod
from .domain import BlockHeader, Chain, TransactionDetails, TransactionReceipt, Transfer

class BlockchainDataFabric(ABC):
    """Provider-independent historical blockchain data contract."""
    @abstractmethod
    async def get_address_transfers(self, address: str, chain: Chain, *, page_size: int = 100,
                                    max_pages: int = 10, max_transactions: int = 500) -> list[Transfer]: ...
    @abstractmethod
    async def get_transaction(self, tx_hash: str, chain: Chain) -> TransactionDetails | None: ...
    @abstractmethod
    async def get_transaction_receipt(self, tx_hash: str, chain: Chain) -> TransactionReceipt | None: ...
    @abstractmethod
    async def get_block(self, block_number: int, chain: Chain) -> BlockHeader | None: ...
