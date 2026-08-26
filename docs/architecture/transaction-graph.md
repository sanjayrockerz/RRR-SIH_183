# Transaction graph and trace intelligence

## Graph model

The graph is a directed NetworkX MultiDiGraph. A node is an observed address with chain, wallet or conservative contract type, first/last seen timestamps, and observed transaction count. An edge is one normalized transfer and retains transaction hash, chain, asset, amount, timestamp, block information, transfer metadata, and an evidence reference. Multiple transactions and assets between the same addresses remain separate edges.

## Traversal and limits

TraceService performs bounded BFS over provider-backed normalized transfers. Forward traversal follows destinations; backward traversal follows sources and analyzes a reversed view for path reconstruction. It applies direction, time window, asset or contract filter, asset-local amount threshold, hop, node, edge, transaction, and duration limits. A limit hit produces PARTIAL status.

## Paths, flows, and metrics

GraphAnalyzer derives shortest paths, observed fund-flow sequences grouped by asset, node/edge/transaction/asset metrics, inbound/outbound degree primitives, and maximum hop. These are descriptive observations only. They are not risk scores, fraud conclusions, laundering classifications, or entity attribution.

## Persistence and evidence

PostgreSQL remains authoritative. trace_runs records every synchronous run, its parameters/limits, status, provider, and metrics. graph_edges references a specific trace run plus canonical transaction and transfer records. Evidence remains linked to the observed transaction hash and provider. NetworkX is rebuilt for analysis and is never serialized as the source of truth.

## API and UI

The trace endpoint returns nodes, multi-edges, paths, flows, metrics, status, limits, and evidence. Trace listing, graph, path, and metrics endpoints expose persisted analysis. The investigator UI supports bounded trace submission, zoom controls, fit/reset, node selection, edge selection, and an evidence detail panel.

## Scale assumptions

This phase targets bounded investigation graphs, not chain-wide indexing. Limits prevent unbounded traversal. A persistent graph solution is intentionally deferred.
