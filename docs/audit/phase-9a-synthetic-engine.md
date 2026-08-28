# Phase 9A — Synthetic Realtime Engine Audit

## Implementation matrix

| Module | UI | API | Service | Database | Real data | Synthetic data | Status |
|---|---|---|---|---|---|---|---|
| Case registry | Existing | Existing | PostgreSQL repository | PostgreSQL | Historical/provider-dependent | Development fixture | CONNECTED |
| Realtime ingestion | Existing simulated event action | `/api/v1/realtime/simulated/events` | `RealtimeService.receive_simulated` | `realtime_events`, applications, evidence, changesets | Webhook adapter available | Canonical event path | CONNECTED |
| Synthetic engine | New `#dev/realtime` control center | `/api/v1/dev/realtime/*` | `SyntheticBlockchainEventEngine` | Reads/writes through realtime service | Provider replaceable | Deterministic | CONNECTED |
| Graph | Existing graph workspace | Case graph APIs | PostgreSQL/NetworkX + optional Neo4j projection | graph tables | Provider-dependent | Mutated by canonical event | CONNECTED |
| Patterns | Existing page | Pattern APIs | Pattern engine | patterns | Observation-dependent | Event-dependent | CONNECTED |
| Risk | Existing page | Risk APIs | Risk engine | assessments/factors | Observation-dependent | Event-dependent | CONNECTED |
| Alerts | Existing page | Alert APIs | Realtime risk evaluation | alerts | Condition-dependent | Condition-dependent | PARTIAL |
| VASP/sanctions/threat | Existing workspaces | Intelligence APIs | Configured providers | Provenance tables | Credentials/datasets required | No fabricated attribution | NOT_CONFIGURED locally |
| Frontend update | Polling in synthetic control center | Status/events endpoints | 1.5 second refresh | Reads persisted events | Provider-independent | Visible simulation mode | PARTIAL |

## Supported controls

`start`, `pause`, `resume`, `step`, `stop`, scenario start, status and persisted event listing. Scenarios currently include normal activity, rapid hop, fan-out, fan-in, VASP exposure, mixer/bridge-shaped contract movement, escalation and multi-stage sequencing.

Every generated event carries provider `DEVELOPMENT SYNTHETIC` and `raw_provider_reference.source_mode=DEVELOPMENT_SYNTHETIC`. IDs are deterministic for a seed, scenario and event number.

## Known limitations

- The current database event schema does not yet have dedicated columns for `synthetic`, `scenario_id`, `decimals` or `token_id`; these are retained in provider reference metadata where applicable.
- The polling control center is operational and avoids full page refresh, but it is not yet SSE/WebSocket push.
- A generated event creates an alert only when the existing risk engine records a positive risk delta. The engine does not fabricate alerts.
- The generated stream currently mutates persisted realtime state and graph projections; a dedicated stage-duration ledger is not yet persisted.
