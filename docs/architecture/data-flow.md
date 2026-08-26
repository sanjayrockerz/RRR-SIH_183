# Data flow

1. The investigator submits a wallet and trace constraints to the versioned API.
2. FastAPI delegates case, wallet, transaction, edge, and evidence writes to repository interfaces.
3. PostgreSQL persists independent cases, wallets, canonical transactions, case relationships, graph edges, and evidence.
4. The application service invokes BlockchainProvider, never an Alchemy SDK directly.
5. The provider adapter retrieves bounded historical pages and maps them to canonical Transfer records while retaining raw provider references.
6. Transaction, receipt, and block capabilities provide richer historical observations without leaking Alchemy types into the domain.
7. The trace service performs bounded BFS, then persists canonical transactions, asset-transfer rows, graph edges, and evidence references idempotently.
8. Structured signals are returned only when their documented rule conditions are met.
9. The UI labels the result as historical and shows its source and persistence-backed counts.
