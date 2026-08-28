# Investigator experience

The investigator web application is a dark, high-density workstation for authorized blockchain investigations. It preserves the existing API and graph contracts while organizing the available workflow into a persistent application shell.

## Shell and navigation

The shell provides persistent navigation for the dashboard, investigations, wallet intelligence, transaction graph, entities/VASPs, alerts, evidence, and reports. Hash navigation keeps the Phase 0–4 frontend dependency-light and can later be replaced by a router without changing page contracts.

## Current live workflow

`Dashboard → New investigation → manual intake → API case creation → wallet intake → historical trace → case overview → graph inspector`

The Wallet Intelligence workspace provides a read-only lookup over persisted wallet identity and graph observations through `GET /api/v1/wallets/{chain}/{address}`. It reports observed transaction direction counts, assets, related case IDs, timestamps, and evidence counts; it does not infer ownership, current balance, or criminality.

Case and trace data shown in the overview and graph inspector come from the existing FastAPI contracts. Graph nodes, edges, transaction hashes, timestamps, blocks, provider, and evidence references are displayed as observed blockchain flow.

## Capability states

- `HISTORICAL`: current Alchemy-backed retrieval and trace path.
- `LIVE`: reserved for a verified event pipeline; not enabled.
- `SIMULATED`: SAHYOG/NCRP external-system boundary; no external API response is presented as real.
- `NOT CONFIGURED`: a future capability has no connected backend implementation.

SAHYOG/NCRP are represented as a connection boundary only. A future adapter should map an external complaint to a normalized complaint before calling the case service. The UI does not fabricate complaint records, synchronization timestamps, or connection status.

## Workspaces and states

Dashboard, intake, case overview, and graph inspection are operational for the current backend. The case registry can reopen a persisted case through `GET /api/v1/cases/{case_id}` and restore its latest persisted trace into the investigator context. Cases without a trace receive an explicit trace-unavailable state rather than an empty or fabricated graph. Wallet, entity, evidence, alert, and report routes are transparent capability surfaces until their corresponding list, aggregation, and detail APIs exist. Empty, error, disabled, and not-configured states are preferred over fabricated metrics or conclusions.

## Visual and interaction system

The interface uses dark navy surfaces, white typography, restrained blue/cyan accents, thin borders, compact information cards, visible focus states, responsive grids, and reduced-motion-safe transitions. Graph controls expose fit/reset/zoom and node/edge inspection without presenting the graph as a criminality judgment.

## Deliberate scope limits

There is no production authentication/SSO, real-time monitoring, external complaint integration, ML, cross-chain analysis, or new backend attribution logic in this UI phase. Attribution remains source-backed and must come from the existing backend capabilities when wired into a dedicated entity workspace.
