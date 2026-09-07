# RRR Demonstration Flow

This is the verified local development demonstration flow. Present it as synthetic/fixture data unless live provider provenance is separately verified.

## Start

### Docker Compose

```bash
docker compose up --build
```

Compose starts PostgreSQL on host `5433`, Redis, Neo4j on `7474/7687`, FastAPI on `8000`, and Vite on `5173`. The API waits for PostgreSQL and Neo4j health checks.

### Native development

```powershell
# PostgreSQL must be running and DATABASE_URL must point to it
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api
cd apps/investigator-web
npm install
npm run dev -- --host 0.0.0.0
```

## Verify dependencies

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/status
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/integrity
```

Expected audited local state: health 200 and migrations READY; system status DEGRADED because Neo4j is unavailable, TronGrid/realtime/OFAC/threat feeds are not configured; integrity WARN because of orphan relationships in the existing database snapshot.

## Seed deterministic cases

```powershell
$seed = Invoke-RestMethod http://127.0.0.1:8000/api/v1/dev/hardcoded-cases `
  -Method Post -ContentType 'application/json' -Body '{}'
$seed | ConvertTo-Json -Depth 6
```

The endpoint is idempotent by external reference and uses the regular PostgreSQL trace/graph/pattern/risk pipeline. It creates:

| Scenario | Expected primary path | Expected persisted shape |
|---|---|---|
| `DEMO-MIXER-CRITICAL` | ROOT -> intermediary -> mixer -> intermediary -> Demo Exchange | 5 nodes, 4 edges, 10.00/9.80/9.60/9.40 ETH |
| `DEMO-BRIDGE-HIGH` | ROOT -> intermediary -> bridge -> destination wallet -> intermediary -> Demo Exchange | 6 nodes, 5 edges, bridge and destination-chain metadata |
| `DEMO-NORMAL-LOW` | ROOT -> wallet -> wallet -> Demo Exchange | 4 nodes, 3 edges, 1.00/0.95/0.90 ETH |

The exact case IDs are returned by the endpoint and should be copied into the existing case selector. Do not hardcode UUIDs into a presentation script because a new database generates new IDs.

## Operational intelligence surfaces

After seeding, open the command center and verify that its cards and triage queue are populated from persisted case, risk, watch, alert, attribution, cross-chain, and timeline records:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/dashboard/intelligence
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/cases/$caseId/intelligence"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/cases/$caseId/vasp-candidates"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/risk-registry/search?q=DEMO"
```

The snapshot consolidates persisted risk, patterns, related-case overlap, watches, alerts, cross-chain context, and rule-based recommendations. VASP candidates are ranked observations with provenance and evidence paths; they are not ownership or guilt findings. The action package creates a report/evidence snapshot for investigator review and does not freeze assets or contact a VASP automatically. Risk Registry is internal investigative memory, not a blacklist.

## Walkthrough

1. Open the returned case ID from the case selector.
2. Confirm the overview, transaction count and case ID.
3. Open Transactions and select a transaction to show hash, block, timestamp, amount, asset and chain.
4. Open Graph. Confirm the primary path is one directed flow and the endpoint shows the source-backed Demo Exchange attribution.
5. Open Fund Flow and Patterns. Explain that patterns are observations over persisted trace edges, not criminality conclusions.
6. Open Risk. Show the persisted calculated score, band, factors and evidence links. Do not describe the score as a probability.
7. Open Realtime. Explain that development events are explicitly synthetic. Live Alchemy webhook status is configuration-dependent.
8. Open Cross-chain. Explain that bridge correlation requires explicit source/destination observations; the demo bridge metadata is deterministic development data.
9. Open Evidence and Timeline. Show evidence IDs, source, capture time, hash/manifest state and timeline events.
10. Generate a report and download the PDF. Explain that it is a point-in-time snapshot of persisted data.
11. Return to the command center. Show the backend-ranked triage queue and open Risk Registry. From the case snapshot, open VASP Intelligence and show candidate confidence, source quality, evidence-path hashes, limitations, and the review-only action package.

## Judge explanation

The user submits a suspect wallet. RRR keeps the same case ID while it acquires or receives transaction observations, normalizes them, stores them, selects a directed primary path, applies behavioral observations and source-backed attribution, calculates a rule-based risk posture, monitors subsequent events and produces a report. Synthetic cases and unconfigured external intelligence must be called out explicitly.

The bridge fixture is explicitly marked development synthetic. A demo correlation is not proof of a live bridge protocol integration.

## Stop and reset

Do not delete broad database directories or volumes during a demonstration. To reset only a known development case, use `DELETE /api/v1/dev/seed-case/{case_id}` after confirming the exact ID. PostgreSQL and Neo4j data volumes are persistent under Compose.
