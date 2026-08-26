# Cross-Chain Correlation

`CrossChainCorrelationEngine` compares a source bridge interaction with destination-chain normalized transfers. It considers message ID, recipient, asset, amount, and bounded time windows. Correlation levels are `EXACT`, `STRONG`, `PROBABLE`, `POSSIBLE`, and `UNRESOLVED`.

Timing or symbol matching is not proof of a bridge-mediated movement. The API and UI preserve the reasons and mark every link `INFERRED`. `POSSIBLE` and `UNRESOLVED` relationships are not used as established destinations.
