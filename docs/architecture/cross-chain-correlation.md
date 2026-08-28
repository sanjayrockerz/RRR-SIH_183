# Cross-Chain Correlation

Correlation records are idempotent. The correlation ID is derived from the source transaction, destination transaction, and bridge identity; the persisted link UUID is deterministically derived from that correlation ID. Repeating analysis therefore returns the same logical link and cannot create duplicate cross-chain relationships. An unresolved bridge interaction uses a separate deterministic unresolved key and does not assert a destination address.

Destination-chain scope is fail-closed: an interaction without an explicit destination chain produces `UNRESOLVED`, even when timing or asset symbols look similar. Asset-symbol equality is only a weak correlation reason and never establishes chain identity or an asset mapping by itself.

`CrossChainCorrelationEngine` compares a source bridge interaction with destination-chain normalized transfers. It considers message ID, recipient, asset, amount, and bounded time windows. Correlation levels are `EXACT`, `STRONG`, `PROBABLE`, `POSSIBLE`, and `UNRESOLVED`.

Timing or symbol matching is not proof of a bridge-mediated movement. The API and UI preserve the reasons and mark every link `INFERRED`. `POSSIBLE` and `UNRESOLVED` relationships are not used as established destinations.
