# RRR System Audit

Updated: 2026-08-26

Scope: repository inspection of `apps/api`, `apps/investigator-web`, PostgreSQL migrations, providers, services, tests, configuration, Docker, and documentation. This is a factual maturity audit, not a claim that every UI surface is production-ready.

## Executive summary

RRR has a real, evidence-first historical investigation core. The most complete path is:

```text
manual intake → FastAPI → Alchemy adapter → normalized transfers
→ bounded NetworkX trace → PostgreSQL transactions/edges/evidence
→ patterns → deterministic risk assessment → investigator UI
```

Realtime and cross-chain modules are implemented boundaries with explicit configuration gates. They are not universally live in the default environment. PostgreSQL runtime validation is currently blocked by local credentials, so deployment readiness is not established.

## Capability maturity matrix

| Capability | Frontend | API | Service | DB | External provider | Status | Required work |
|---|---|---|---|---|---|---|---|
| Cases | Manual intake; case registry | Create/read/list/patch/close/reopen | Repository-backed | PostgreSQL | None | IMPLEMENTED + PARTIALLY CONNECTED | Add assignment, description UI, authorization |
| Wallets | Intake and graph inspection | Validate/add/deduplicate | Case repository + trace service | `wallets`, `case_wallets` | Alchemy/TronGrid boundary | IMPLEMENTED + CONNECTED for Ethereum | Add wallet intelligence profile and cross-case query |
| Transactions | Trace/graph views | Intake, normalized trace persistence | Data fabric + trace | `transactions`, transfers, case links | Alchemy | IMPLEMENTED + CONNECTED for bounded history | Add transaction-forensics endpoint and broader provider fallback |
| Graph | NetworkX inspector; Neo4j APIs ready | Trace/graph/path/metrics plus projection/query APIs | Bounded NetworkX analysis + optional Neo4j projection | `graph_edges`, trace runs plus Neo4j projection | Normalized provider data | IMPLEMENTED + PARTIALLY CONNECTED | Add realtime projection, rebuild/checkpoint tooling, and UI query controls |
| Neo4j | Graph API not yet surfaced in UI | Projection status, project, neighbors, shortest-path APIs | Optional idempotent projection service | Separate graph store | Neo4j | IMPLEMENTED + NOT CONFIGURED | Add realtime projection, rebuild/checkpoint tooling, and UI query controls |
| Entities | Attribution surfaces | Entity/catalog/address attribution APIs | Curated attribution engine | Attribution tables | Curated/public source | IMPLEMENTED + PARTIALLY CONNECTED | Add source ingestion/versioning and entity UI |
| VASP attribution | Partial nearest-entity result | Attribution endpoints | Confidence/provenance resolver | Address attribution records | Curated dataset | IMPLEMENTED + PARTIALLY CONNECTED | Commercial adapters only behind explicit contracts |
| Patterns | Patterns workspace | Analyze/list/summary/detail | Modular bounded detectors | Pattern observations/evidence | Trace observations | IMPLEMENTED + CONNECTED | Add full evidence navigation and notes |
| Risk | Risk workspace | Assess/history/delta/factors/alerts | Deterministic rule engine | Risk assessment/factor tables | Patterns/attributions | IMPLEMENTED + CONNECTED | Add provider intelligence as separate factors, never hidden score inputs |
| Alerts | Live persisted alert queue plus realtime surface | Alert and risk-candidate APIs | Realtime and risk boundaries | `alerts`, candidates | Alchemy webhook if configured | IMPLEMENTED + PARTIALLY CONNECTED | Complete investigator review workflow and notifications |
| Realtime | Monitoring workspace | Signed webhook, simulated event, watches | Idempotent/reorg-aware application | Realtime/watch/timeline tables | Alchemy Address Activity | IMPLEMENTED + PARTIALLY CONNECTED | Configure webhook, retries/DLQ, confirmation policy, live UI stream |
| Evidence | Capability surface plus graph references | Evidence persisted through trace/realtime | Evidence creation/linking | `evidence` and join tables | Provider raw references | IMPLEMENTED + PARTIALLY CONNECTED | Evidence vault, immutable export manifest, content hashes |
| Reports | Connected report preview | Generate/list/get APIs | Evidence-backed snapshot service | `investigation_reports` | Persisted case evidence/pattern/risk records | Implemented + partially connected | Add authenticated export, templates, and retention policy |
| SAHYOG | Explicit simulated adapter boundary | No live adapter | None | Case fields can hold external reference | No authorized API | SIMULATED / NOT CONFIGURED | Obtain official API contract and credentials |
| NCRP | Explicit simulated adapter boundary | No live adapter | None | Case fields can hold external reference | No authorized API | SIMULATED / NOT CONFIGURED | Obtain official API contract and credentials |
| Cross-chain | Cross-chain workspace | Chain, observation, analyze, links, paths APIs | Ethereum/Tron boundary and correlation | Migration 008 tables | TronGrid/curated bridge definitions | IMPLEMENTED + PARTIALLY CONNECTED | Configure Tron and approved bridge definitions; validate end-to-end |
| Cyber intelligence | No connected UI | None | None | None | None | MISSING | Add threat provider contract, provenance records, curated source first |
| Sanctions | No connected UI | None | None | None | OFAC not ingested | MISSING | Add versioned OFAC ingestion and direct/indirect/unknown semantics |
| Authentication | No enforced login | No identity middleware | None | No actor enforcement | None | MISSING / PRODUCTION BLOCKED | OIDC/SSO boundary, sessions, token validation |
| RBAC | UI initials only | No authorization checks | None | No case access policy | None | MISSING / PRODUCTION BLOCKED | ADMIN/INVESTIGATOR/SUPERVISOR/ANALYST/READ_ONLY policy |
| Audit | Case audit read surface | Persisted audit-event API | Service action events + request IDs | `audit_events`, timeline | None | Implemented + partial actor context | OIDC actor identity, before/after diffs, and access enforcement |
| Observability | Basic status notice | `/health`, system status, capabilities | Logging | No metrics tables | Provider responses | IMPLEMENTED + PARTIALLY CONNECTED | Structured request IDs, latency/error metrics, provider health history |

## UI-to-backend findings

- Dashboard headline metrics are intentionally empty or capability-labeled; they are not yet backed by aggregate APIs.
- Intake is connected to case creation, wallet validation, trace retrieval, and trace persistence, but depends on PostgreSQL and Alchemy configuration.
- Cases now loads the persisted case index and exposes backend errors instead of silently presenting fixture rows.
- Graph, patterns, risk, realtime, and cross-chain pages call real APIs when a case/trace exists; their live capability depends on persisted state and provider configuration.
- Wallets, entities, evidence, alerts, reports, and several command-center surfaces remain partial or capability-ready rather than complete investigator workspaces.
- SAHYOG/NCRP must remain visibly simulated/not configured until an authorized adapter exists.

## Runtime blockers

1. Local PostgreSQL rejects the configured `postgres` password; database integration tests remain skipped.
2. Alchemy credentials are not assumed to exist.
3. Realtime webhook registration is external to the repository.
4. Tron and bridge definitions are not live by default.
5. Authentication and authorization are absent.

## Audit conclusion

The platform is suitable for continued engineering and controlled demo use with explicitly marked capability states. It is not ready for deployment with sensitive law-enforcement data until database validation, identity/access control, evidence export controls, and operational observability are completed.
