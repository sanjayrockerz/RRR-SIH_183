from datetime import datetime, timezone
from uuid import UUID, uuid4
import json
import logging
from pathlib import Path
import asyncpg
from .config import settings
from .domain import *
from .services import CaseRepository
from .risk_persistence import RiskPersistenceMixin
from .realtime_persistence import RealtimePersistenceMixin
from .cross_chain_persistence import CrossChainPersistenceMixin
from .cyber_persistence import CyberPersistenceMixin
from .evidence_persistence import EvidencePersistenceMixin
from .report_persistence import ReportPersistenceMixin

class DatabaseError(RuntimeError):
    """Database failures safe to translate at the HTTP boundary."""

class PostgresCaseRepository(ReportPersistenceMixin, EvidencePersistenceMixin, CyberPersistenceMixin, CrossChainPersistenceMixin, RealtimePersistenceMixin, RiskPersistenceMixin, CaseRepository):
    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self.status = "UNAVAILABLE"
        self.migration_status = "UNKNOWN"
        self.last_error: str | None = None
    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(settings.database_url, min_size=settings.database_min_pool_size, max_size=settings.database_max_pool_size)
            if settings.database_auto_migrate: await self._run_migrations()
            self.status = "READY"; self.migration_status = "READY"; self.last_error = None
        except (OSError, asyncpg.PostgresError) as exc:
            self.status = "UNAVAILABLE"; self.migration_status = "UNKNOWN"; self.last_error = type(exc).__name__
            if self.pool: await self.pool.close(); self.pool = None
            logging.getLogger("crypto_fraud_intelligence").error("database_error",extra={"error_type":type(exc).__name__})
    async def close(self):
        if self.pool: await self.pool.close()
        self.pool = None
    async def _run_migrations(self):
        pool=self._require_pool()
        candidates = [Path.cwd() / "infrastructure" / "postgres"]
        resolved = Path(__file__).resolve()
        candidates.extend([parent / "infrastructure" / "postgres" for parent in resolved.parents])
        directory = next((candidate for candidate in candidates if candidate.exists()), None)
        if directory is None:
            raise DatabaseError("PostgreSQL migration directory is unavailable")
        async with pool.acquire() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            applied={row["version"] for row in await conn.fetch("SELECT version FROM schema_migrations")}
            for path in sorted(directory.glob("*.sql")):
                if path.name in applied: continue
                async with conn.transaction():
                    await conn.execute(path.read_text(encoding="utf-8"))
                    await conn.execute("INSERT INTO schema_migrations(version) VALUES($1)",path.name)
    def _require_pool(self):
        if not self.pool: raise DatabaseError("Persistent storage is unavailable")
        return self.pool
    def _json_dict(self, value):
        if isinstance(value, str):
            try: return json.loads(value)
            except json.JSONDecodeError: return {}
        return value or {}
    async def create(self, data: CaseCreate) -> InvestigationCase:
        case_id=uuid4(); now=datetime.now(timezone.utc); pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO cases(case_id,title,description,external_case_id,created_by,fraud_type,status,priority,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$9)",case_id,data.title,data.description,data.external_case_reference,data.created_by,data.fraud_type,"OPEN",data.priority,now)
            result=await self.get(str(case_id)); assert result; return result
        except asyncpg.PostgresError as exc: raise DatabaseError("Case could not be persisted") from exc

    async def delete_case(self, case_id: str) -> bool:
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                result = await conn.execute("DELETE FROM cases WHERE case_id=$1", UUID(case_id))
            return result.endswith("1")
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Case could not be deleted") from exc
    async def list_cases(self) -> list[CaseListItem]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("""SELECT c.case_id,c.title,c.fraud_type,c.priority,c.status,c.created_at,c.updated_at,c.external_case_id,
                    (SELECT count(*) FROM case_wallets cw WHERE cw.case_id=c.case_id) AS wallet_count,
                    (SELECT count(*) FROM case_transactions ct WHERE ct.case_id=c.case_id) AS transaction_count,
                    (SELECT w.address FROM wallets w JOIN case_wallets cw ON cw.wallet_id=w.wallet_id WHERE cw.case_id=c.case_id ORDER BY w.address LIMIT 1) AS wallet_address,
                    (SELECT ra.risk_band FROM risk_assessments ra WHERE ra.case_id=c.case_id ORDER BY ra.version DESC LIMIT 1) AS risk_band,
                    c.workflow_stage
                    FROM cases c ORDER BY c.updated_at DESC""")
            return [CaseListItem(case_id=str(r["case_id"]),title=r["title"],fraud_type=r["fraud_type"],priority=r["priority"],status=r["status"],created_at=r["created_at"],updated_at=r["updated_at"],wallet_count=r["wallet_count"],transaction_count=r["transaction_count"],external_case_reference=r["external_case_id"],wallet_address=r["wallet_address"],risk_band=r["risk_band"],workflow_stage=r["workflow_stage"]) for r in rows]
        except asyncpg.PostgresError as exc: raise DatabaseError("Cases could not be retrieved") from exc
    async def dashboard_summary(self) -> DashboardSummary:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("""SELECT
                    (SELECT count(*) FROM cases WHERE status <> 'CLOSED') AS active_cases,
                    (SELECT count(*) FROM wallets) AS wallets_under_review,
                    (SELECT count(*) FROM alerts WHERE status='NEW' AND severity IN ('HIGH','CRITICAL'))
                      + (SELECT count(*) FROM risk_alert_candidates WHERE status='NEW' AND severity IN ('HIGH','CRITICAL')) AS high_priority_alerts,
                    (SELECT count(*) FROM entities) AS attributed_entities,
                    (SELECT count(*) FROM transactions WHERE status='OBSERVED') AS observed_transactions,
                    (SELECT count(*) FROM watch_targets WHERE status='ACTIVE') AS active_watches,
                    (SELECT GREATEST(COALESCE((SELECT max(timestamp) FROM investigation_timeline), 'epoch'::timestamptz), COALESCE((SELECT max(timestamp) FROM transactions), 'epoch'::timestamptz))) AS last_activity_at,
                    (SELECT count(*) FROM cases WHERE created_at >= NOW() - INTERVAL '1 day') AS investigations_today,
                    (SELECT count(DISTINCT addr) FROM (SELECT source_wallet AS addr FROM graph_edges UNION SELECT destination_wallet AS addr FROM graph_edges) u) AS graph_nodes,
                    (SELECT count(*) FROM graph_edges) AS graph_edges,
                    (SELECT count(*) FROM alerts WHERE status='NEW') AS open_alerts,
                    (SELECT count(*) FROM cases WHERE priority IN ('HIGH', 'CRITICAL') AND status <> 'CLOSED') AS critical_cases,
                    (SELECT row_to_json(r) FROM (SELECT t.tx_hash, t.chain, tt.amount, tt.asset, tt.created_at AS timestamp FROM transaction_transfers tt JOIN transactions t ON t.transaction_id=tt.transaction_id ORDER BY tt.created_at DESC LIMIT 1) r) AS latest_blockchain_event,
                    (SELECT row_to_json(t) FROM (SELECT edge_id, case_id, source_wallet, destination_wallet, amount, asset FROM graph_edges ORDER BY created_at DESC LIMIT 1) t) AS latest_graph_mutation,
                    (SELECT row_to_json(t) FROM (SELECT pattern_id, pattern_type, severity, description FROM pattern_observations ORDER BY created_at DESC LIMIT 1) t) AS latest_pattern,
                    (SELECT row_to_json(t) FROM (SELECT assessment_id, score, risk_band AS band, calculated_at FROM risk_assessments ORDER BY calculated_at DESC LIMIT 1) t) AS latest_risk_change,
                    (SELECT row_to_json(t) FROM (SELECT alert_id, title, severity, created_at FROM alerts ORDER BY created_at DESC LIMIT 1) t) AS latest_alert
                """)
            
            last=row["last_activity_at"]
            
            def parse_json(val):
                if not val:
                    return None
                return json.loads(val) if isinstance(val, str) else val

            return DashboardSummary(
                active_cases=row["active_cases"] or 0,
                wallets_under_review=row["wallets_under_review"] or 0,
                high_priority_alerts=row["high_priority_alerts"] or 0,
                attributed_entities=row["attributed_entities"] or 0,
                observed_transactions=row["observed_transactions"] or 0,
                active_watches=row["active_watches"] or 0,
                last_activity_at=None if last and last.year==1970 else last,
                investigations_today=row["investigations_today"] or 0,
                wallets_under_investigation=row["wallets_under_review"] or 0,
                transactions_analyzed=row["observed_transactions"] or 0,
                graph_nodes=row["graph_nodes"] or 0,
                graph_edges=row["graph_edges"] or 0,
                open_alerts=row["open_alerts"] or 0,
                critical_cases=row["critical_cases"] or 0,
                latest_blockchain_event=parse_json(row["latest_blockchain_event"]),
                latest_graph_mutation=parse_json(row["latest_graph_mutation"]),
                latest_pattern=parse_json(row["latest_pattern"]),
                latest_risk_change=parse_json(row["latest_risk_change"]),
                latest_alert=parse_json(row["latest_alert"])
            )
        except asyncpg.PostgresError as exc: raise DatabaseError("Dashboard summary could not be retrieved") from exc

    async def dashboard_intelligence(self, limit: int = 20) -> DashboardIntelligence:
        """Return one backend-owned operational read model for the command center.

        All signals are derived from persisted case, risk, watch, alert, attribution,
        cross-chain, timeline, and exact-overlap records. Missing signals remain null
        or zero with an explicit status; the UI must not manufacture them.
        """
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                totals = await conn.fetchrow("""
                    WITH latest_risk AS (
                      SELECT DISTINCT ON (case_id) case_id, risk_band, score, score_delta
                      FROM risk_assessments ORDER BY case_id, version DESC
                    ), vasp_addresses AS (
                      SELECT DISTINCT aa.chain, lower(aa.address) AS address, ent.entity_id,
                        ent.name, ent.entity_type, aa.confidence, aa.source_reference
                      FROM address_attributions aa JOIN entities ent ON ent.entity_id=aa.entity_id
                      WHERE ent.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE')
                    )
                    SELECT
                      (SELECT count(*) FROM cases c LEFT JOIN latest_risk r ON r.case_id=c.case_id
                       WHERE c.status <> 'CLOSED' AND (c.priority='CRITICAL' OR r.risk_band='CRITICAL')) AS critical_cases,
                      (SELECT count(*) FROM watch_targets WHERE status='ACTIVE') AS active_watches,
                      (SELECT count(DISTINCT (c.case_id, va.entity_id)) FROM cases c
                       JOIN graph_edges ge ON ge.case_id=c.case_id
                       JOIN transactions gt ON gt.transaction_id=ge.transaction_id
                       JOIN vasp_addresses va ON va.chain=gt.chain AND va.address IN (lower(ge.source_wallet), lower(ge.destination_wallet))) AS vasp_leads,
                      (SELECT count(DISTINCT (c.case_id, va.entity_id)) FROM cases c
                       JOIN graph_edges ge ON ge.case_id=c.case_id
                       JOIN transactions gt ON gt.transaction_id=ge.transaction_id
                       JOIN vasp_addresses va ON va.chain=gt.chain AND va.address IN (lower(ge.source_wallet), lower(ge.destination_wallet))
                       WHERE va.confidence IN ('HIGH','CONFIRMED')) AS high_confidence_vasp_leads,
                      (SELECT count(DISTINCT case_id) FROM cross_chain_links) AS cross_chain_cases,
                      (SELECT count(*) FROM cross_chain_links WHERE correlation_level IN ('UNRESOLVED','NONE')) AS unresolved_cross_chain_cases,
                      (SELECT count(*) FROM (
                        SELECT DISTINCT other.case_id FROM case_wallets current JOIN case_wallets other ON other.wallet_id=current.wallet_id WHERE current.case_id<>other.case_id
                        UNION
                        SELECT DISTINCT other.case_id FROM case_transactions current JOIN case_transactions other ON other.transaction_id=current.transaction_id WHERE current.case_id<>other.case_id
                      ) overlap_rows) AS related_case_clusters,
                      (SELECT count(*) FROM alerts WHERE status='NEW') AS open_alerts,
                      (SELECT count(*) FROM alerts WHERE status='NEW' AND severity='CRITICAL') AS critical_alerts
                """)
                rows = await conn.fetch("""
                    WITH latest_risk AS (
                      SELECT DISTINCT ON (case_id) case_id, risk_band, score, score_delta, calculated_at
                      FROM risk_assessments ORDER BY case_id, version DESC
                    ), latest_vasp AS (
                      SELECT DISTINCT ON (ge.case_id) ge.case_id, ent.entity_id, ent.name, ent.entity_type,
                        gt.chain, COALESCE(ge.hop, 0) AS hop_distance, aa.confidence, aa.source_reference, gt.tx_hash
                      FROM graph_edges ge
                      JOIN transactions gt ON gt.transaction_id=ge.transaction_id
                      JOIN address_attributions aa ON aa.chain=gt.chain AND lower(aa.address) IN (lower(ge.source_wallet), lower(ge.destination_wallet))
                      JOIN entities ent ON ent.entity_id=aa.entity_id
                      WHERE ent.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE')
                      ORDER BY ge.case_id, COALESCE(ge.hop, 0), aa.confidence DESC
                    ), related AS (
                      SELECT current.case_id, count(DISTINCT other.case_id) AS related_case_count
                      FROM case_wallets current JOIN case_wallets other ON other.wallet_id=current.wallet_id
                      WHERE current.case_id<>other.case_id GROUP BY current.case_id
                    ), related_tx AS (
                      SELECT current.case_id, count(DISTINCT other.case_id) AS related_case_count
                      FROM case_transactions current JOIN case_transactions other ON other.transaction_id=current.transaction_id
                      WHERE current.case_id<>other.case_id GROUP BY current.case_id
                    ), base AS (
                      SELECT c.case_id, c.title, c.external_case_id, c.fraud_type, c.status, c.priority, c.workflow_stage,
                        r.risk_band, r.score, COALESCE(r.score_delta,0) AS risk_delta,
                        CASE WHEN EXISTS (SELECT 1 FROM watch_targets w WHERE w.case_id=c.case_id AND w.status='ACTIVE') THEN 'ACTIVE' ELSE 'NOT_CONFIGURED' END AS watch_state,
                        GREATEST(c.updated_at, COALESCE((SELECT max(t.timestamp) FROM investigation_timeline t WHERE t.case_id=c.case_id), c.updated_at)) AS latest_activity_at,
                        CASE WHEN v.entity_id IS NULL THEN 0 ELSE 1 END AS vasp_lead_count,
                        CASE WHEN v.entity_id IS NULL THEN NULL ELSE jsonb_build_object('entity_id',v.entity_id::text,'entity_name',v.name,'entity_type',v.entity_type,'chain',v.chain,'hop_distance',v.hop_distance,'confidence',v.confidence,'source',v.source_reference,'transaction_hash',v.tx_hash) END AS nearest_vasp,
                        GREATEST(COALESCE(rel.related_case_count,0), COALESCE(relt.related_case_count,0)) AS related_case_count,
                        (SELECT count(*) FROM alerts a WHERE a.case_id=c.case_id AND a.status='NEW' AND a.severity='CRITICAL') AS open_critical_alerts
                      FROM cases c LEFT JOIN latest_risk r ON r.case_id=c.case_id LEFT JOIN latest_vasp v ON v.case_id=c.case_id
                        LEFT JOIN related rel ON rel.case_id=c.case_id LEFT JOIN related_tx relt ON relt.case_id=c.case_id
                      WHERE c.status <> 'CLOSED'
                    )
                    SELECT *, row_number() OVER (ORDER BY
                      CASE WHEN risk_band='CRITICAL' OR priority='CRITICAL' THEN 1 ELSE 0 END DESC,
                      CASE WHEN risk_band='HIGH' OR priority='HIGH' THEN 1 ELSE 0 END DESC,
                      CASE WHEN watch_state='ACTIVE' THEN 1 ELSE 0 END DESC,
                      CASE WHEN vasp_lead_count>0 THEN 1 ELSE 0 END DESC,
                      open_critical_alerts DESC, risk_delta DESC, latest_activity_at DESC) AS priority_rank
                    FROM base
                    ORDER BY priority_rank LIMIT $1
                """, max(1, min(limit, 100)))
                events = await conn.fetch("""SELECT case_id::text AS case_id, event_type, summary, source, timestamp
                    FROM investigation_timeline ORDER BY timestamp DESC LIMIT 12""")
                movements = await conn.fetch("""SELECT case_id::text AS case_id, score, risk_band, score_delta, calculated_at
                    FROM risk_assessments WHERE score_delta IS NOT NULL ORDER BY calculated_at DESC LIMIT 12""")
                factor_rows = await conn.fetch("""
                    WITH latest AS (
                      SELECT DISTINCT ON (case_id) assessment_id
                      FROM risk_assessments ORDER BY case_id, version DESC
                    )
                    SELECT rf.name, SUM(rf.contribution)::float AS contribution,
                      MAX(rf.max_contribution)::float AS max_contribution,
                      COUNT(DISTINCT rfe.evidence_id)::int AS evidence_count
                    FROM latest l
                    JOIN risk_factors rf ON rf.assessment_id=l.assessment_id
                    LEFT JOIN risk_factor_evidence rfe ON rfe.factor_id=rf.factor_id
                    GROUP BY rf.name ORDER BY contribution DESC LIMIT 8
                """)

            def json_value(value):
                if not value: return None
                return json.loads(value) if isinstance(value, str) else value
            priority_cases = []
            for row in rows:
                reasons = []
                if row["risk_band"] in {"CRITICAL", "HIGH"}: reasons.append(f"{row['risk_band']} persisted risk posture")
                if float(row["risk_delta"] or 0) > 0: reasons.append(f"risk increased +{float(row['risk_delta']):g}")
                if row["watch_state"] == "ACTIVE": reasons.append("active watch")
                if row["vasp_lead_count"]: reasons.append("source-backed VASP lead")
                if row["open_critical_alerts"]: reasons.append("open critical alert")
                priority_cases.append(PriorityCase(case_id=str(row["case_id"]), title=row["title"], external_case_reference=row["external_case_id"], fraud_type=row["fraud_type"], status=row["status"], workflow_stage=row["workflow_stage"], risk_band=row["risk_band"], risk_score=float(row["score"]) if row["score"] is not None else None, risk_delta=float(row["risk_delta"] or 0), watch_state=row["watch_state"], latest_activity_at=row["latest_activity_at"], vasp_lead_count=row["vasp_lead_count"], nearest_vasp=json_value(row["nearest_vasp"]), related_case_count=row["related_case_count"] or 0, open_critical_alerts=row["open_critical_alerts"] or 0, priority_rank=row["priority_rank"], priority_reason="; ".join(reasons) if reasons else "No persisted priority signals are available."))
            return DashboardIntelligence(status="READY", critical_cases=totals["critical_cases"] or 0, active_watches=totals["active_watches"] or 0, vasp_leads=totals["vasp_leads"] or 0, high_confidence_vasp_leads=totals["high_confidence_vasp_leads"] or 0, cross_chain_cases=totals["cross_chain_cases"] or 0, unresolved_cross_chain_cases=totals["unresolved_cross_chain_cases"] or 0, related_case_clusters=totals["related_case_clusters"] or 0, open_alerts=totals["open_alerts"] or 0, critical_alerts=totals["critical_alerts"] or 0, priority_cases=priority_cases, recent_intelligence_events=[dict(item) for item in events], risk_movements=[dict(item) for item in movements], risk_factor_summary=[dict(item) for item in factor_rows], generated_at=datetime.now(timezone.utc))
        except asyncpg.PostgresError as exc:
            raise DatabaseError("Dashboard intelligence could not be retrieved") from exc

    async def risk_registry_search(self, query: str = "", kind: str = "ALL", limit: int = 50) -> RiskRegistryResponse:
        """Search persisted investigative memory without assigning criminal labels."""
        pool = self._require_pool()
        normalized_kind = kind.upper()
        if normalized_kind not in {"ALL", "WALLET", "ENTITY", "VASP", "CASE", "TRANSACTION"}:
            raise ValueError("kind must be ALL, WALLET, ENTITY, VASP, CASE, or TRANSACTION")
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    WITH wallet_rows AS (
                      SELECT 'WALLET'::text AS record_type, w.wallet_id::text AS record_id, w.address AS label, w.chain::text AS chain,
                        count(DISTINCT cw.case_id)::int AS observed_case_count,
                        min(t.timestamp) AS first_observed, max(t.timestamp) AS last_observed,
                        max(ra.score)::float AS highest_investigative_risk,
                        (array_agg(ra.score ORDER BY ra.calculated_at DESC) FILTER (WHERE ra.score IS NOT NULL))[1]::float AS current_investigative_risk,
                        COALESCE(array_agg(DISTINCT aa.role::text) FILTER (WHERE aa.role IS NOT NULL), ARRAY[]::text[]) AS observed_roles,
                        COALESCE(array_agg(DISTINCT ent.name) FILTER (WHERE ent.name IS NOT NULL), ARRAY[]::text[]) AS related_vasps,
                        COALESCE(array_agg(DISTINCT cw.case_id::text), ARRAY[]::text[]) AS connected_case_ids,
                        (SELECT count(*)::int FROM evidence e WHERE e.case_id IN (SELECT case_id FROM case_wallets WHERE wallet_id=w.wallet_id)) AS evidence_count
                      FROM wallets w
                      LEFT JOIN case_wallets cw ON cw.wallet_id=w.wallet_id
                      LEFT JOIN case_transactions ct ON ct.case_id=cw.case_id
                      LEFT JOIN transactions t ON t.transaction_id=ct.transaction_id AND ((w.chain='ethereum' AND (lower(t.from_address)=lower(w.address) OR lower(t.to_address)=lower(w.address))) OR (w.chain<>'ethereum' AND (t.from_address=w.address OR t.to_address=w.address)))
                      LEFT JOIN risk_assessments ra ON ra.case_id=cw.case_id AND ((w.chain='ethereum' AND lower(ra.subject_address)=lower(w.address)) OR (w.chain<>'ethereum' AND ra.subject_address=w.address))
                      LEFT JOIN address_attributions aa ON aa.chain=w.chain AND ((w.chain='ethereum' AND lower(aa.address)=lower(w.address)) OR (w.chain<>'ethereum' AND aa.address=w.address))
                      LEFT JOIN entities ent ON ent.entity_id=aa.entity_id AND ent.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE')
                      GROUP BY w.wallet_id,w.address,w.chain
                    ), entity_rows AS (
                      SELECT CASE WHEN e.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE') THEN 'VASP' ELSE 'ENTITY' END::text AS record_type,
                        e.entity_id::text AS record_id, e.name AS label, NULL::text AS chain, count(DISTINCT ge.case_id)::int AS observed_case_count,
                        min(ge.timestamp) AS first_observed, max(ge.timestamp) AS last_observed, max(ra.score)::float AS highest_investigative_risk,
                        (array_agg(ra.score ORDER BY ra.calculated_at DESC) FILTER (WHERE ra.score IS NOT NULL))[1]::float AS current_investigative_risk,
                        COALESCE(array_agg(DISTINCT aa.role::text), ARRAY[]::text[]) AS observed_roles,
                        ARRAY[e.name]::text[] AS related_vasps, COALESCE(array_agg(DISTINCT ge.case_id::text), ARRAY[]::text[]) AS connected_case_ids,
                        (SELECT count(*)::int FROM evidence ev WHERE ev.case_id IN (SELECT DISTINCT ge2.case_id FROM graph_edges ge2 JOIN transactions tx2 ON tx2.transaction_id=ge2.transaction_id JOIN address_attributions aa2 ON aa2.entity_id=e.entity_id AND aa2.chain=tx2.chain AND lower(aa2.address) IN (lower(ge2.source_wallet),lower(ge2.destination_wallet)))) AS evidence_count
                      FROM entities e JOIN address_attributions aa ON aa.entity_id=e.entity_id
                      LEFT JOIN graph_edges ge ON lower(aa.address) IN (lower(ge.source_wallet),lower(ge.destination_wallet))
                      LEFT JOIN transactions tx ON tx.transaction_id=ge.transaction_id AND tx.chain=aa.chain
                      LEFT JOIN risk_assessments ra ON ra.case_id=ge.case_id
                      GROUP BY e.entity_id,e.name,e.entity_type
                    ), case_rows AS (
                      SELECT 'CASE'::text AS record_type, c.case_id::text AS record_id, COALESCE(c.external_case_id,c.title) AS label, NULL::text AS chain,
                        count(DISTINCT cw.wallet_id)::int AS observed_case_count, min(c.created_at) AS first_observed, max(c.updated_at) AS last_observed,
                        (SELECT score::float FROM risk_assessments WHERE case_id=c.case_id ORDER BY calculated_at DESC LIMIT 1) AS highest_investigative_risk,
                        (SELECT score::float FROM risk_assessments WHERE case_id=c.case_id ORDER BY calculated_at DESC LIMIT 1) AS current_investigative_risk,
                        ARRAY[]::text[] AS observed_roles, ARRAY[]::text[] AS related_vasps, ARRAY[c.case_id::text] AS connected_case_ids,
                        (SELECT count(*)::int FROM evidence WHERE case_id=c.case_id) AS evidence_count
                      FROM cases c LEFT JOIN case_wallets cw ON cw.case_id=c.case_id GROUP BY c.case_id,c.external_case_id,c.title
                    ), transaction_rows AS (
                      SELECT 'TRANSACTION'::text AS record_type, t.transaction_id::text AS record_id, t.tx_hash AS label, t.chain::text AS chain,
                        count(DISTINCT ct.case_id)::int AS observed_case_count, t.timestamp AS first_observed, t.timestamp AS last_observed,
                        NULL::float AS highest_investigative_risk, NULL::float AS current_investigative_risk, ARRAY[]::text[] AS observed_roles,
                        ARRAY[]::text[] AS related_vasps, COALESCE(array_agg(DISTINCT ct.case_id::text), ARRAY[]::text[]) AS connected_case_ids,
                        (SELECT count(*)::int FROM evidence WHERE lower(tx_hash)=lower(t.tx_hash)) AS evidence_count
                      FROM transactions t LEFT JOIN case_transactions ct ON ct.transaction_id=t.transaction_id GROUP BY t.transaction_id,t.tx_hash,t.chain,t.timestamp
                    ), all_rows AS (SELECT * FROM wallet_rows UNION ALL SELECT * FROM entity_rows UNION ALL SELECT * FROM case_rows UNION ALL SELECT * FROM transaction_rows)
                    SELECT * FROM all_rows WHERE ($1='' OR label ILIKE '%' || $1 || '%' OR record_id ILIKE '%' || $1 || '%') AND ($2='ALL' OR record_type=$2) ORDER BY last_observed DESC NULLS LAST, label LIMIT $3
                """, query.strip(), normalized_kind, max(1, min(limit, 200)))
            entries = [RiskRegistryEntry(record_type=row["record_type"], record_id=row["record_id"], label=row["label"], address=row["label"] if row["record_type"] == "WALLET" else None, chain=row["chain"], observed_case_count=row["observed_case_count"] or 0, first_observed=row["first_observed"], last_observed=row["last_observed"], highest_investigative_risk=row["highest_investigative_risk"], current_investigative_risk=row["current_investigative_risk"], observed_roles=list(row["observed_roles"] or []), related_vasps=list(row["related_vasps"] or []), connected_case_ids=list(row["connected_case_ids"] or []), evidence_count=row["evidence_count"] or 0) for row in rows]
            return RiskRegistryResponse(status="READY", query=query, entries=entries, generated_at=datetime.now(timezone.utc))
        except asyncpg.PostgresError as exc:
            raise DatabaseError("Risk registry search could not be completed") from exc

    async def case_transactions(self, case_id: str, limit: int = 500, offset: int = 0, chain: str | None = None, asset: str | None = None, status: str | None = None, wallet: str | None = None, direction: str | None = None, search: str | None = None, start: datetime | None = None, end: datetime | None = None) -> list[CaseTransactionView]:
        """Canonical ledger data. This deliberately reads persisted rows, not a trace/UI projection."""
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("""WITH latest_risk AS (
                    SELECT assessment_id FROM risk_assessments WHERE case_id=$1 ORDER BY calculated_at DESC LIMIT 1
                  )
                  SELECT t.transaction_id,t.tx_hash,t.chain,t.block_number,t.timestamp,t.status,t.from_address,t.to_address,t.provider,
                    tt.asset,tt.amount,tt.transfer_type,tt.contract_address,tt.token_id,tt.decimals,
                    COALESCE(array_agg(DISTINCT e.evidence_id) FILTER (WHERE e.evidence_id IS NOT NULL), ARRAY[]::uuid[]) AS evidence_ids,
                    COALESCE((
                      SELECT jsonb_agg(DISTINCT jsonb_build_object(
                        'factor_id',rf.factor_id::text,
                        'name',rf.name,
                        'category',rf.category,
                        'contribution',rf.contribution,
                        'confidence_level',rf.confidence_level,
                        'evidence_ids',COALESCE((SELECT jsonb_agg(rfe.evidence_id::text) FROM risk_factor_evidence rfe WHERE rfe.factor_id=rf.factor_id),'[]'::jsonb),
                        'pattern_ids',COALESCE((SELECT jsonb_agg(rfp.pattern_id::text) FROM risk_factor_patterns rfp WHERE rfp.factor_id=rf.factor_id),'[]'::jsonb)
                      ))
                      FROM risk_factors rf
                      JOIN latest_risk lr ON lr.assessment_id=rf.assessment_id
                      WHERE EXISTS (
                        SELECT 1 FROM risk_factor_transactions rft
                        WHERE rft.factor_id=rf.factor_id AND lower(rft.transaction_hash)=lower(t.tx_hash)
                      )
                      OR EXISTS (
                        SELECT 1 FROM risk_factor_evidence rfe JOIN evidence re ON re.evidence_id=rfe.evidence_id
                        WHERE rfe.factor_id=rf.factor_id AND lower(re.tx_hash)=lower(t.tx_hash)
                      )
                    ), '[]'::jsonb) AS risk_factors,
                    COALESCE((
                      SELECT jsonb_agg(DISTINCT jsonb_build_object(
                        'pattern_id',po.pattern_id::text,
                        'pattern_type',po.pattern_type,
                        'severity',po.severity,
                        'confidence_level',po.confidence_level,
                        'description',po.description
                      ))
                      FROM pattern_observations po
                      JOIN pattern_observation_evidence poe ON poe.pattern_id=po.pattern_id
                      JOIN evidence pe ON pe.evidence_id=poe.evidence_id
                      WHERE po.case_id=ct.case_id AND lower(pe.tx_hash)=lower(t.tx_hash)
                    ), '[]'::jsonb) AS pattern_observations,
                    COALESCE((
                      SELECT jsonb_agg(DISTINCT jsonb_build_object(
                        'entity_id',ent.entity_id::text,
                        'name',ent.name,
                        'entity_type',ent.entity_type,
                        'role',aa.role,
                        'confidence',aa.confidence,
                        'address',aa.address,
                        'source_reference',aa.source_reference
                      ))
                      FROM address_attributions aa
                      JOIN entities ent ON ent.entity_id=aa.entity_id
                      WHERE aa.chain=t.chain AND (
                        lower(aa.address)=lower(t.from_address) OR lower(aa.address)=lower(t.to_address)
                      )
                    ), '[]'::jsonb) AS entity_exposure
                    FROM case_transactions ct JOIN transactions t ON t.transaction_id=ct.transaction_id
                    LEFT JOIN transaction_transfers tt ON tt.transaction_id=t.transaction_id
                    LEFT JOIN evidence e ON e.case_id=ct.case_id AND e.tx_hash=t.tx_hash
                    WHERE ct.case_id=$1
                      AND ($2::text IS NULL OR t.chain=$2)
                      AND ($3::text IS NULL OR tt.asset=$3)
                      AND ($4::text IS NULL OR t.status=$4)
                      AND ($5::text IS NULL OR ($6::text='IN' AND lower(t.to_address)=lower($5)) OR ($6::text='OUT' AND lower(t.from_address)=lower($5)) OR ($6::text NOT IN ('IN','OUT') AND (lower(t.to_address)=lower($5) OR lower(t.from_address)=lower($5))))
                      AND ($7::text IS NULL OR lower(t.tx_hash) LIKE '%' || lower($7) || '%' OR lower(t.from_address) LIKE '%' || lower($7) || '%' OR lower(t.to_address) LIKE '%' || lower($7) || '%')
                      AND ($8::timestamptz IS NULL OR t.timestamp >= $8)
                      AND ($9::timestamptz IS NULL OR t.timestamp <= $9)
                    GROUP BY ct.case_id,t.transaction_id,t.tx_hash,t.chain,t.block_number,t.timestamp,t.status,t.from_address,t.to_address,t.provider,tt.asset,tt.amount,tt.transfer_type,tt.contract_address,tt.token_id,tt.decimals
                    ORDER BY t.timestamp DESC NULLS LAST, t.created_at DESC LIMIT $10 OFFSET $11""",UUID(case_id),chain,asset,status,wallet,(direction or '').upper(),search,start,end,max(1,min(limit,1000)),max(0,offset))
            result=[]
            for row in rows:
                factors=self._json_dict(row['risk_factors']) if not isinstance(row['risk_factors'], list) else row['risk_factors']
                patterns=self._json_dict(row['pattern_observations']) if not isinstance(row['pattern_observations'], list) else row['pattern_observations']
                entities=self._json_dict(row['entity_exposure']) if not isinstance(row['entity_exposure'], list) else row['entity_exposure']
                if isinstance(factors, dict): factors=[]
                if isinstance(patterns, dict): patterns=[]
                if isinstance(entities, dict): entities=[]
                score=round(min(100,float(sum(float(item.get('contribution') or 0) for item in factors))),2)
                if score >= 80: band="CRITICAL"
                elif score >= 60: band="HIGH"
                elif score >= 40: band="ELEVATED"
                elif score >= 20: band="GUARDED"
                else: band="LOW"
                result.append(CaseTransactionView(case_id=case_id,transaction_id=str(row['transaction_id']),tx_hash=row['tx_hash'],chain=row['chain'],block_number=row['block_number'],timestamp=row['timestamp'],status=row['status'],from_address=row['from_address'],to_address=row['to_address'],asset=row['asset'] or 'UNKNOWN',amount=row['amount'] or '0',transfer_type=row['transfer_type'] or 'native',contract_address=row['contract_address'],token_id=row['token_id'],decimals=row['decimals'],provider=row['provider'],observed_at=row['timestamp'],evidence_ids=[str(item) for item in row['evidence_ids']],risk_score=score,risk_band=band,risk_factors=factors,pattern_observations=patterns,entity_exposure=entities))
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Case transactions could not be retrieved") from exc

    async def case_summary_counts(self, case_id: str) -> dict:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("""SELECT
                    (SELECT count(*) FROM case_wallets WHERE case_id=$1) wallets,
                    (SELECT count(*) FROM case_transactions WHERE case_id=$1) transactions,
                    (SELECT count(*) FROM (SELECT source_wallet AS address FROM graph_edges WHERE case_id=$1 UNION SELECT destination_wallet AS address FROM graph_edges WHERE case_id=$1) graph_nodes) graph_nodes,
                    (SELECT count(*) FROM graph_edges WHERE case_id=$1) graph_edges,
                    (SELECT count(*) FROM pattern_observations WHERE case_id=$1) patterns,
                    (SELECT count(*) FROM alerts WHERE case_id=$1) alerts,
                    (SELECT count(*) FROM evidence WHERE case_id=$1) evidence,
                    (SELECT count(DISTINCT e.event_id) FROM realtime_events e JOIN realtime_event_applications a ON a.event_id=e.event_id WHERE a.case_id=$1) realtime_events,
                    (SELECT count(*) FROM watch_targets WHERE case_id=$1 AND status='ACTIVE') active_watches""",UUID(case_id))
            return dict(row)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Case summary could not be retrieved") from exc

    async def database_integrity(self) -> dict:
        pool = self._require_pool()
        tables = {
            "cases": "cases", "wallets": "wallets", "transactions": "transactions",
            "transfers": "transaction_transfers", "graph_edges": "graph_edges", "trace_runs": "trace_runs",
            "patterns": "pattern_observations", "risk_assessments": "risk_assessments", "risk_factors": "risk_factors",
            "watch_targets": "watch_targets", "realtime_events": "realtime_events", "alerts": "alerts",
            "evidence": "evidence", "workflow_events": "case_workflow_events",
        }
        try:
            async with pool.acquire() as conn:
                counts = {}
                for key, table in tables.items():
                    counts[key] = (await conn.fetchval(f"SELECT count(*) FROM {table}"))
                orphans = {
                    "transactions_without_case": await conn.fetchval("SELECT count(*) FROM transactions t WHERE NOT EXISTS (SELECT 1 FROM case_transactions ct WHERE ct.transaction_id=t.transaction_id)"),
                    "evidence_without_case": await conn.fetchval("SELECT count(*) FROM evidence e WHERE NOT EXISTS (SELECT 1 FROM cases c WHERE c.case_id=e.case_id)"),
                    "graph_edges_without_transaction": await conn.fetchval("SELECT count(*) FROM graph_edges ge WHERE NOT EXISTS (SELECT 1 FROM transactions t WHERE t.transaction_id=ge.transaction_id)"),
                    "risk_factors_without_evidence": await conn.fetchval("SELECT count(*) FROM risk_factors rf WHERE NOT EXISTS (SELECT 1 FROM risk_factor_evidence rfe WHERE rfe.factor_id=rf.factor_id)"),
                }
            return {"status": "CONNECTED", "counts": counts, "orphans": orphans, "orphan_total": sum(orphans.values())}
        except asyncpg.PostgresError as exc:
            raise DatabaseError("Database integrity diagnostics failed") from exc

    async def audit_events(self, case_id: str) -> list[AuditEvent]:
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM audit_events WHERE case_id=$1 ORDER BY occurred_at DESC", UUID(case_id))
            return [AuditEvent(event_id=str(row["event_id"]), case_id=str(row["case_id"]) if row["case_id"] else None, action=row["action"], resource_type=row["resource_type"], resource_id=row["resource_id"], actor_id=row["actor_id"], occurred_at=row["occurred_at"], metadata=(json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}))) for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Audit events could not be retrieved") from exc

    async def related_cases(self, case_id: str) -> list[CaseLink]:
        pool = self._require_pool()
        try:
            case_uuid = UUID(case_id)
            async with pool.acquire() as conn:
                wallet_rows = await conn.fetch("""SELECT other.case_id, w.chain, w.address FROM case_wallets current JOIN wallets w ON w.wallet_id=current.wallet_id JOIN case_wallets other ON other.wallet_id=current.wallet_id WHERE current.case_id=$1 AND other.case_id<>$1 ORDER BY other.case_id,w.chain,w.address""", case_uuid)
                tx_rows = await conn.fetch("""SELECT other.case_id, t.chain, t.tx_hash FROM case_transactions current JOIN transactions t ON t.transaction_id=current.transaction_id JOIN case_transactions other ON other.transaction_id=current.transaction_id WHERE current.case_id=$1 AND other.case_id<>$1 ORDER BY other.case_id,t.chain,t.tx_hash""", case_uuid)
                case_rows = await conn.fetch("SELECT case_id,title FROM cases WHERE case_id IN (SELECT DISTINCT other.case_id FROM case_wallets current JOIN case_wallets other ON other.wallet_id=current.wallet_id WHERE current.case_id=$1 AND other.case_id<>$1 UNION SELECT DISTINCT other.case_id FROM case_transactions current JOIN case_transactions other ON other.transaction_id=current.transaction_id WHERE current.case_id=$1 AND other.case_id<>$1)", case_uuid)
            grouped = {}
            for row in wallet_rows:
                grouped.setdefault(str(row["case_id"]), {"wallets": [], "transactions": []})["wallets"].append({"chain": row["chain"], "address": row["address"]})
            for row in tx_rows:
                grouped.setdefault(str(row["case_id"]), {"wallets": [], "transactions": []})["transactions"].append({"chain": row["chain"], "tx_hash": row["tx_hash"]})
            titles = {str(row["case_id"]): row["title"] for row in case_rows}
            now = datetime.now(timezone.utc)
            result = []
            for related_id, values in grouped.items():
                wallets = list({(item["chain"], item["address"]): item for item in values["wallets"]}.values())
                transactions = list({(item["chain"], item["tx_hash"]): item for item in values["transactions"]}.values())
                relationship = "SHARED_WALLET_AND_TRANSACTION" if wallets and transactions else ("SHARED_WALLET" if wallets else "SHARED_TRANSACTION")
                basis = []
                if wallets: basis.append(f"{len(wallets)} exact persisted wallet identity match(es)")
                if transactions: basis.append(f"{len(transactions)} exact persisted transaction identity match(es)")
                result.append(CaseLink(link_id=f"{case_id}:{related_id}", case_id=case_id, related_case_id=related_id, relationship_type=relationship, shared_wallets=wallets, shared_transactions=transactions, explanation=f"Case {case_id} has {', '.join(basis)} with case {related_id} ({titles.get(related_id, 'title unavailable')}). This is an observed data overlap, not a conclusion about common control or criminality.", created_at=now))
            return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Related cases could not be retrieved") from exc

    async def case_fusion_fingerprints(self, case_id: str | None = None) -> list[CaseFingerprint]:
        """Read one bounded, aggregate fingerprint per case for deterministic Case Fusion."""
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT c.case_id::text AS case_id,
                      COALESCE((SELECT array_agg(DISTINCT cw.wallet_id::text ORDER BY cw.wallet_id::text) FROM case_wallets cw WHERE cw.case_id=c.case_id), ARRAY[]::text[]) AS wallet_ids,
                      COALESCE((SELECT array_agg(DISTINCT ct.transaction_id::text ORDER BY ct.transaction_id::text) FROM case_transactions ct WHERE ct.case_id=c.case_id), ARRAY[]::text[]) AS transaction_ids,
                      COALESCE((SELECT array_agg(DISTINCT aa.entity_id::text ORDER BY aa.entity_id::text)
                        FROM graph_edges ge JOIN transactions tx ON tx.transaction_id=ge.transaction_id JOIN address_attributions aa ON aa.chain=tx.chain AND ((ge.source_wallet=aa.address) OR (ge.destination_wallet=aa.address) OR (tx.chain='ethereum' AND (lower(ge.source_wallet)=lower(aa.address) OR lower(ge.destination_wallet)=lower(aa.address))))
                        WHERE ge.case_id=c.case_id), ARRAY[]::text[]) AS entity_ids,
                      COALESCE((SELECT array_agg(DISTINCT aa.entity_id::text ORDER BY aa.entity_id::text)
                        FROM graph_edges ge JOIN transactions tx ON tx.transaction_id=ge.transaction_id JOIN address_attributions aa ON aa.chain=tx.chain AND ((ge.source_wallet=aa.address) OR (ge.destination_wallet=aa.address) OR (tx.chain='ethereum' AND (lower(ge.source_wallet)=lower(aa.address) OR lower(ge.destination_wallet)=lower(aa.address))))
                        JOIN entities en ON en.entity_id=aa.entity_id WHERE ge.case_id=c.case_id AND en.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE')), ARRAY[]::text[]) AS vasp_ids,
                      COALESCE((SELECT array_agg(DISTINCT x.bridge_id ORDER BY x.bridge_id) FROM (SELECT bridge_id FROM bridge_interactions WHERE case_id=c.case_id UNION SELECT bridge_id FROM cross_chain_links WHERE case_id=c.case_id) x), ARRAY[]::text[]) AS bridge_ids,
                      COALESCE((SELECT array_agg(DISTINCT tx.chain ORDER BY tx.chain) FROM graph_edges ge JOIN transactions tx ON tx.transaction_id=ge.transaction_id WHERE ge.case_id=c.case_id), ARRAY[]::text[]) AS chains,
                      COALESCE((SELECT array_agg(DISTINCT po.pattern_type ORDER BY po.pattern_type) FROM pattern_observations po WHERE po.case_id=c.case_id), ARRAY[]::text[]) AS pattern_types,
                      (SELECT min(ge.timestamp) FROM graph_edges ge WHERE ge.case_id=c.case_id) AS first_activity,
                      (SELECT max(ge.timestamp) FROM graph_edges ge WHERE ge.case_id=c.case_id) AS last_activity,
                      jsonb_build_object('edge_count',(SELECT count(*) FROM graph_edges ge WHERE ge.case_id=c.case_id),'transaction_count',(SELECT count(DISTINCT ge.transaction_id) FROM graph_edges ge WHERE ge.case_id=c.case_id)) AS burst_profile,
                      COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('wallet_id',w.wallet_id::text,'chain',w.chain,'address',w.address)) FROM case_wallets cw JOIN wallets w ON w.wallet_id=cw.wallet_id WHERE cw.case_id=c.case_id), '[]'::jsonb) AS wallets,
                      COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('entity_id',en.entity_id::text,'name',en.name,'entity_type',en.entity_type,'chain',aa.chain,'address',aa.address,'confidence',aa.confidence,'source_reference',aa.source_reference))
                        FROM graph_edges ge JOIN transactions tx ON tx.transaction_id=ge.transaction_id JOIN address_attributions aa ON aa.chain=tx.chain AND ((ge.source_wallet=aa.address) OR (ge.destination_wallet=aa.address) OR (tx.chain='ethereum' AND (lower(ge.source_wallet)=lower(aa.address) OR lower(ge.destination_wallet)=lower(aa.address)))) JOIN entities en ON en.entity_id=aa.entity_id WHERE ge.case_id=c.case_id AND en.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE')), '[]'::jsonb) AS vasps,
                      COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('bridge_id',x.bridge_id,'name',COALESCE(bd.name,x.bridge_id),'source',COALESCE(bd.source,'UNKNOWN'))) FROM (SELECT bridge_id FROM bridge_interactions WHERE case_id=c.case_id UNION SELECT bridge_id FROM cross_chain_links WHERE case_id=c.case_id) x LEFT JOIN bridge_definitions bd ON bd.bridge_id=x.bridge_id), '[]'::jsonb) AS bridges
                    FROM cases c
                    WHERE ($1::uuid IS NULL OR c.case_id=$1::uuid)
                    ORDER BY c.created_at
                """, UUID(case_id) if case_id else None)
            def json_value(value):
                return json.loads(value) if isinstance(value, str) else (value or [])
            return [CaseFingerprint(case_id=row['case_id'], wallet_ids=list(row['wallet_ids'] or []), transaction_ids=list(row['transaction_ids'] or []), entity_ids=list(row['entity_ids'] or []), vasp_ids=list(row['vasp_ids'] or []), bridge_ids=list(row['bridge_ids'] or []), chains=list(row['chains'] or []), pattern_types=list(row['pattern_types'] or []), first_activity=row['first_activity'], last_activity=row['last_activity'], burst_profile=json_value(row['burst_profile']), wallets=json_value(row['wallets']), vasps=json_value(row['vasps']), bridges=json_value(row['bridges'])) for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Case Fusion fingerprints could not be retrieved") from exc
    async def list_evidence(self, case_id: str) -> list[Evidence]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM evidence WHERE case_id=$1 ORDER BY captured_at DESC",UUID(case_id))
            return [Evidence(evidence_id=str(r["evidence_id"]),case_id=case_id,type=r["evidence_type"],chain=r["chain"],tx_hash=r["tx_hash"],source=r["source"],captured_at=r["captured_at"],metadata=(json.loads(r["metadata"]) if isinstance(r["metadata"],str) else (r["metadata"] or {})),content_hash=r.get("content_hash"),integrity_status=r.get("integrity_status") or "UNVERIFIED") for r in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Evidence could not be retrieved") from exc
    async def update_case(self, case_id: str, data: CasePatch) -> InvestigationCase | None:
        pool=self._require_pool(); case_uuid=UUID(case_id); changes=data.model_dump(exclude_unset=True)
        columns={"title":"title","fraud_type":"fraud_type","priority":"priority","description":"description","external_case_reference":"external_case_id"}
        try:
            async with pool.acquire() as conn:
                values=[]; sets=[]
                for key,value in changes.items():
                    if key in columns:
                        values.append(value); sets.append(f"{columns[key]}=${len(values)+1}")
                if sets:
                    await conn.execute(f"UPDATE cases SET {', '.join(sets)},updated_at=${len(values)+1} WHERE case_id=${len(values)+2}",*values,datetime.now(timezone.utc),case_uuid)
            return await self.get(case_id)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Case could not be updated") from exc
    async def _set_case_status(self, case_id: str, status: str) -> InvestigationCase | None:
        pool=self._require_pool(); case_uuid=UUID(case_id); now=datetime.now(timezone.utc)
        try:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE cases SET status=$1,closed_at=$2,updated_at=$3 WHERE case_id=$4",status,now if status=="CLOSED" else None,now,case_uuid)
            return await self.get(case_id)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Case status could not be updated") from exc
    async def close_case(self, case_id: str): return await self._set_case_status(case_id,"CLOSED")
    async def reopen_case(self, case_id: str): return await self._set_case_status(case_id,"INVESTIGATING")
    async def set_workflow_stage(self, case_id: str, stage: CaseWorkflowStage, provider: str | None = None, result_count: int | None = None, error: str | None = None, evidence_ids: list[str] | None = None):
        pool=self._require_pool(); case_uuid=UUID(case_id); now=datetime.now(timezone.utc)
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    exists=await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid)
                    if not exists: return None
                    await conn.execute("UPDATE cases SET workflow_stage=$1,updated_at=$2 WHERE case_id=$3",stage,now,case_uuid)
                    await conn.execute("INSERT INTO case_workflow_events(event_id,case_id,stage,started_at,completed_at,provider,result_count,error,evidence_ids) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",uuid4(),case_uuid,stage,now,now,provider,result_count,error,json.dumps(evidence_ids or []))
            return await self.get(case_id)
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Case workflow stage could not be persisted") from exc
    async def workflow_events(self, case_id: str):
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT * FROM case_workflow_events WHERE case_id=$1 ORDER BY started_at DESC",UUID(case_id))
            return [{"event_id":str(row["event_id"]),"case_id":str(row["case_id"]),"stage":row["stage"],"started_at":row["started_at"],"completed_at":row["completed_at"],"provider":row["provider"],"result_count":row["result_count"],"error":row["error"],"evidence_ids":json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or [])} for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Case workflow history could not be retrieved") from exc
    async def get(self, case_id: str) -> InvestigationCase | None:
        pool=self._require_pool()
        try:
            case_uuid=UUID(case_id)
            async with pool.acquire() as conn:
                row=await conn.fetchrow("SELECT * FROM cases WHERE case_id=$1",case_uuid)
                if not row: return None
                wallet_rows=await conn.fetch("SELECT w.chain,w.address FROM wallets w JOIN case_wallets cw ON cw.wallet_id=w.wallet_id WHERE cw.case_id=$1 ORDER BY w.address",case_uuid)
                tx_rows=await conn.fetch("SELECT t.chain,t.tx_hash FROM transactions t JOIN case_transactions ct ON ct.transaction_id=t.transaction_id WHERE ct.case_id=$1 ORDER BY t.created_at",case_uuid)
                trace_run=await conn.fetchrow("SELECT trace_id, mode, provider, acquisition FROM trace_runs WHERE case_id=$1 ORDER BY completed_at DESC LIMIT 1",case_uuid)
                latest_trace_id = trace_run["trace_id"] if trace_run else None
                edge_rows=await conn.fetch("SELECT ge.*,t.chain,t.tx_hash,t.block_number,t.timestamp,t.from_address,t.to_address,t.native_value,t.fee,t.provider,t.raw_reference,tt.transfer_type,tt.contract_address,tt.token_id,tt.decimals,tt.raw_reference AS transfer_raw_reference FROM graph_edges ge JOIN transactions t ON t.transaction_id=ge.transaction_id LEFT JOIN transaction_transfers tt ON tt.transaction_id=ge.transaction_id AND tt.source_address=ge.source_wallet AND tt.destination_address=ge.destination_wallet AND tt.asset=ge.asset AND tt.amount=ge.amount WHERE ge.case_id=$1 AND ($2::uuid IS NULL OR ge.trace_id=$2 OR ge.trace_id IS NULL) ORDER BY ge.created_at",case_uuid,latest_trace_id)
                evidence_rows=await conn.fetch("SELECT * FROM evidence WHERE case_id=$1 ORDER BY created_at",case_uuid)
            latest_trace=self._trace_from_rows(
                str(case_uuid), wallet_rows, edge_rows, evidence_rows,
                str(latest_trace_id) if latest_trace_id else "",
                acquisition=trace_run["acquisition"] if trace_run else None,
                trace_mode=trace_run["mode"] if trace_run else DataMode.HISTORICAL,
                trace_provider=trace_run["provider"] if trace_run else "Persisted provider observation"
            ) if edge_rows or evidence_rows or trace_run else None
            return InvestigationCase(case_id=str(row["case_id"]),title=row["title"],fraud_type=row["fraud_type"],priority=row["priority"],status=row["status"],created_at=row["created_at"],updated_at=row["updated_at"],external_case_reference=row.get("external_case_id"),description=row.get("description"),created_by=row.get("created_by"),closed_at=row.get("closed_at"),workflow_stage=row.get("workflow_stage") or CaseWorkflowStage.NEW, wallets=[WalletCreate(address=r["address"],chain=r["chain"]) for r in wallet_rows],transactions=[TransactionCreate(tx_hash=r["tx_hash"],chain=r["chain"]) for r in tx_rows],latest_trace=latest_trace)
        except ValueError: return None
        except asyncpg.PostgresError as exc: raise DatabaseError("Case could not be retrieved") from exc
    async def add_wallet(self, case_id: str, wallet: WalletCreate) -> InvestigationCase:
        pool=self._require_pool(); case_uuid=UUID(case_id); address=normalize_address(wallet.chain,wallet.address)
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid): return None
                    existing=await conn.fetchval("SELECT wallet_id FROM wallets WHERE chain=$1 AND address=$2",wallet.chain,address)
                    if not existing: existing=await conn.fetchval("INSERT INTO wallets(wallet_id,chain,address,created_at) VALUES($1,$2,$3,$4) RETURNING wallet_id",uuid4(),wallet.chain,address,datetime.now(timezone.utc))
                    await conn.execute("INSERT INTO case_wallets(case_id,wallet_id,role,created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",case_uuid,existing,"REPORTED",datetime.now(timezone.utc))
            result=await self.get(case_id); assert result; return result
        except asyncpg.PostgresError as exc: raise DatabaseError("Wallet could not be persisted") from exc

    async def wallet_intelligence(self, chain: Chain, address: str):
        try:
            async with self._require_pool().acquire() as conn:
                row=await conn.fetchrow("""
                    SELECT w.wallet_id,w.chain,w.address,
                      (SELECT min(g.timestamp) FROM graph_edges g WHERE g.source_wallet=$2 OR g.destination_wallet=$2) AS first_seen,
                      (SELECT max(g.timestamp) FROM graph_edges g WHERE g.source_wallet=$2 OR g.destination_wallet=$2) AS last_seen,
                      (SELECT count(DISTINCT g.transaction_id) FROM graph_edges g WHERE g.source_wallet=$2 OR g.destination_wallet=$2) AS transaction_count,
                      (SELECT count(*) FROM graph_edges g WHERE g.destination_wallet=$2) AS inbound_count,
                      (SELECT count(*) FROM graph_edges g WHERE g.source_wallet=$2) AS outbound_count,
                      (SELECT COALESCE(array_agg(DISTINCT g.asset ORDER BY g.asset), ARRAY[]::text[]) FROM graph_edges g WHERE g.source_wallet=$2 OR g.destination_wallet=$2) AS assets,
                      (SELECT count(DISTINCT cw.case_id) FROM case_wallets cw WHERE cw.wallet_id=w.wallet_id) AS case_count,
                      (SELECT COALESCE(array_agg(DISTINCT cw.case_id::text ORDER BY cw.case_id::text), ARRAY[]::text[]) FROM case_wallets cw WHERE cw.wallet_id=w.wallet_id) AS related_case_ids,
                      (SELECT count(DISTINCT e.evidence_id) FROM evidence e WHERE e.chain=$1 AND e.tx_hash IN (SELECT DISTINCT t.tx_hash FROM transactions t JOIN graph_edges g ON g.transaction_id=t.transaction_id WHERE g.source_wallet=$2 OR g.destination_wallet=$2)) AS evidence_count
                    FROM wallets w WHERE w.chain=$1 AND w.address=$2
                """,chain,address)
            if not row: return None
            return WalletIntelligence(wallet_id=str(row["wallet_id"]),chain=row["chain"],address=row["address"],first_seen=row["first_seen"],last_seen=row["last_seen"],transaction_count=row["transaction_count"],inbound_count=row["inbound_count"],outbound_count=row["outbound_count"],assets=list(row["assets"] or []),case_count=row["case_count"],related_case_ids=list(row["related_case_ids"] or []),evidence_count=row["evidence_count"])
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Wallet intelligence could not be retrieved") from exc

    async def risk_registry_wallet(self, chain: Chain, address: str) -> RiskRegistryEntry | None:
        """Return chain-aware wallet memory from persisted graph, risk and case records."""
        try:
            async with self._require_pool().acquire() as conn:
                row = await conn.fetchrow("""
                    WITH target AS (SELECT wallet_id,address,chain FROM wallets WHERE chain=$1 AND address=$2),
                    cases_for_wallet AS (SELECT cw.case_id FROM case_wallets cw JOIN target w ON w.wallet_id=cw.wallet_id),
                    activity AS (SELECT DISTINCT ge.case_id,ge.transaction_id,ge.timestamp,ge.asset,ge.source_wallet,ge.destination_wallet FROM graph_edges ge JOIN transactions tx ON tx.transaction_id=ge.transaction_id JOIN target w ON ge.case_id IN (SELECT case_id FROM cases_for_wallet) AND ((w.chain='ethereum' AND tx.chain='ethereum' AND (lower(ge.source_wallet)=lower(w.address) OR lower(ge.destination_wallet)=lower(w.address))) OR (w.chain<>'ethereum' AND tx.chain=w.chain AND (ge.source_wallet=w.address OR ge.destination_wallet=w.address)))),
                    risks AS (SELECT ra.* FROM risk_assessments ra JOIN cases_for_wallet c ON c.case_id=ra.case_id),
                    attributed AS (SELECT DISTINCT en.entity_id::text AS entity_id,en.name,en.entity_type,aa.chain,aa.address,aa.confidence,aa.source_reference FROM address_attributions aa JOIN entities en ON en.entity_id=aa.entity_id JOIN activity a ON a.case_id IN (SELECT case_id FROM cases_for_wallet) AND ((aa.chain='ethereum' AND (lower(aa.address)=lower(a.source_wallet) OR lower(aa.address)=lower(a.destination_wallet))) OR (aa.chain<>'ethereum' AND (aa.address=a.source_wallet OR aa.address=a.destination_wallet))) WHERE aa.chain=$1 AND en.entity_type IN ('VASP','EXCHANGE','CUSTODIAL_SERVICE','SERVICE'))
                    SELECT w.wallet_id::text AS wallet_id,w.address,w.chain,
                      (SELECT min(timestamp) FROM activity) AS first_observed,(SELECT max(timestamp) FROM activity) AS last_observed,
                      (SELECT count(DISTINCT tr.trace_id)::int FROM trace_runs tr JOIN cases_for_wallet cf ON cf.case_id=tr.case_id) AS trace_count,
                      (SELECT count(DISTINCT transaction_id)::int FROM activity) AS transaction_count,
                      (SELECT count(DISTINCT case_id)::int FROM cases_for_wallet) AS observed_case_count,
                      (SELECT max(score)::float FROM risks) AS highest_score,
                      (SELECT (array_agg(risk_band ORDER BY score DESC))[1] FROM risks) AS highest_band,
                      (SELECT (array_agg(score ORDER BY calculated_at DESC))[1]::float FROM risks) AS latest_score,
                      (SELECT (array_agg(risk_band ORDER BY calculated_at DESC))[1] FROM risks) AS latest_band,
                      COALESCE((SELECT array_agg(DISTINCT assessment_id::text ORDER BY assessment_id::text) FROM risks),ARRAY[]::text[]) AS risk_history,
                      COALESCE((SELECT array_agg(DISTINCT po.pattern_type ORDER BY po.pattern_type) FROM pattern_observations po JOIN cases_for_wallet cf ON cf.case_id=po.case_id),ARRAY[]::text[]) AS patterns,
                      COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('entity_id',entity_id,'name',name,'entity_type',entity_type,'chain',chain,'address',address,'confidence',confidence,'source_reference',source_reference)) FROM attributed),'[]'::jsonb) AS entities,
                      COALESCE((SELECT array_agg(DISTINCT name ORDER BY name) FROM attributed),ARRAY[]::text[]) AS vasps,
                      COALESCE((SELECT array_agg(DISTINCT bridge_id ORDER BY bridge_id) FROM (SELECT bridge_id FROM bridge_interactions WHERE case_id IN (SELECT case_id FROM cases_for_wallet) UNION SELECT bridge_id FROM cross_chain_links WHERE case_id IN (SELECT case_id FROM cases_for_wallet)) b),ARRAY[]::text[]) AS bridges,
                      COALESCE((SELECT array_agg(DISTINCT case_id::text ORDER BY case_id::text) FROM cases_for_wallet),ARRAY[]::text[]) AS related_cases,
                      (SELECT count(DISTINCT e.evidence_id)::int FROM evidence e WHERE e.case_id IN (SELECT case_id FROM cases_for_wallet)) AS evidence_count,
                      COALESCE((SELECT CASE WHEN count(*)=0 THEN 'NO_DATA' ELSE string_agg(DISTINCT outcome,',') END FROM screening_runs WHERE case_id IN (SELECT case_id FROM cases_for_wallet)),'NOT_CONFIGURED') AS threat_status
                    FROM target w
                    GROUP BY w.wallet_id,w.address,w.chain
                """, chain, address)
            if not row:
                return None
            def json_value(value): return json.loads(value) if isinstance(value, str) else (value or [])
            return RiskRegistryEntry(record_type='WALLET', record_id=row['wallet_id'], label=row['address'], address=row['address'], chain=row['chain'], observed_case_count=row['observed_case_count'] or 0, trace_count=row['trace_count'] or 0, transaction_count=row['transaction_count'] or 0, first_observed=row['first_observed'], last_observed=row['last_observed'], highest_investigative_risk=row['highest_score'], highest_investigative_risk_band=row['highest_band'], current_investigative_risk=row['latest_score'], current_investigative_risk_band=row['latest_band'], risk_history_references=list(row['risk_history'] or []), observed_patterns=list(row['patterns'] or []), associated_entities=json_value(row['entities']), observed_roles=[], related_vasps=list(row['vasps'] or []), associated_bridges=list(row['bridges'] or []), connected_case_ids=list(row['related_cases'] or []), threat_intelligence_status=row['threat_status'] or 'NO_DATA', evidence_count=row['evidence_count'] or 0)
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Risk Registry wallet memory could not be retrieved") from exc
    async def add_transaction(self, case_id: str, transaction: TransactionCreate) -> InvestigationCase:
        pool=self._require_pool(); case_uuid=UUID(case_id); now=datetime.now(timezone.utc)
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid): return None
                    existing=await conn.fetchval("SELECT transaction_id FROM transactions WHERE chain=$1 AND tx_hash=$2",transaction.chain,transaction.tx_hash.lower())
                    if not existing: existing=await conn.fetchval("INSERT INTO transactions(transaction_id,chain,tx_hash,status,from_address,to_address,raw_reference,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING transaction_id",uuid4(),transaction.chain,transaction.tx_hash.lower(),"REPORTED","","",json.dumps({"intake":True}),now)
                    await conn.execute("INSERT INTO case_transactions(case_id,transaction_id,relation_type,created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",case_uuid,existing,"REPORTED",now)
            result=await self.get(case_id); assert result; return result
        except asyncpg.PostgresError as exc: raise DatabaseError("Transaction could not be persisted") from exc
    async def persist_trace(self, result: TraceResult) -> None:
        pool=self._require_pool(); case_uuid=UUID(result.case_id); now=datetime.now(timezone.utc)
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid): raise DatabaseError("Case not found")
                    # Provider acquisition metadata can contain datetime values even
                    # after Pydantic's JSON-mode dump (for example when a provider
                    # supplies a plain dict). PostgreSQL expects valid JSON here, so
                    # normalize any remaining datetime-like values at this boundary.
                    limits_json = json.dumps(result.limits.model_dump(mode='json') if result.limits else {}, default=str)
                    acquisition_data = result.acquisition.model_dump(mode='json') if result.acquisition else {}
                    acquisition_data["predominant_path"] = result.predominant_path
                    acquisition_json = json.dumps(acquisition_data, default=str)
                    await conn.execute("INSERT INTO trace_runs(trace_id,case_id,root_wallet,chain,direction,started_at,completed_at,status,limits,node_count,edge_count,transaction_count,provider,mode,acquisition) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)",UUID(result.trace_id),case_uuid,result.root_address,result.edges[0].transfer.chain if result.edges else Chain.ETHEREUM,result.direction,now,now,result.status,limits_json,result.metrics.node_count,result.metrics.edge_count,result.metrics.unique_transaction_count,result.provider,result.mode,acquisition_json)

                    for edge in result.edges:
                        transfer=edge.transfer
                        tx_id=await conn.fetchval("SELECT transaction_id FROM transactions WHERE chain=$1 AND tx_hash=$2",transfer.chain,transfer.tx_hash.lower())
                        if not tx_id:
                            tx_id=await conn.fetchval("INSERT INTO transactions(transaction_id,chain,tx_hash,block_number,timestamp,status,from_address,to_address,native_value,raw_reference,created_at,provider,provider_retrieved_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING transaction_id",uuid4(),transfer.chain,transfer.tx_hash.lower(),transfer.block_number,transfer.timestamp,"OBSERVED",transfer.source,transfer.destination,transfer.value_native,json.dumps(transfer.raw_reference),now,transfer.provider,now)
                        else:
                            await conn.execute("UPDATE transactions SET block_number=COALESCE($2,block_number),timestamp=COALESCE($3,timestamp),status='OBSERVED',from_address=CASE WHEN $4 <> '' THEN $4 ELSE from_address END,to_address=CASE WHEN $5 <> '' THEN $5 ELSE to_address END,native_value=COALESCE($6,native_value),provider=$7,provider_retrieved_at=$8,raw_reference=CASE WHEN $9::jsonb <> '{}'::jsonb THEN $9::jsonb ELSE raw_reference END WHERE transaction_id=$1",tx_id,transfer.block_number,transfer.timestamp,transfer.source,transfer.destination,transfer.value_native,transfer.provider,now,json.dumps(transfer.raw_reference))
                        await conn.execute("INSERT INTO transaction_transfers(transfer_id,transaction_id,transfer_type,asset,amount,source_address,destination_address,contract_address,token_id,decimals,raw_reference,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT DO NOTHING",uuid4(),tx_id,transfer.transfer_type,transfer.asset,transfer.amount,transfer.source,transfer.destination,transfer.contract_address or "",transfer.token_id or "",transfer.decimals,json.dumps(transfer.raw_reference),now)
                        await conn.execute("INSERT INTO case_transactions(case_id,transaction_id,relation_type,created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",case_uuid,tx_id,"TRACED",now)
                        source_address=normalize_address(transfer.chain,edge.source); destination_address=normalize_address(transfer.chain,edge.target)
                        hop=next((n.depth for n in result.nodes if n.address==source_address),0)
                        await conn.execute("INSERT INTO graph_edges(edge_id,case_id,transaction_id,source_wallet,destination_wallet,asset,amount,timestamp,hop,created_at,trace_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING",uuid4(),case_uuid,tx_id,source_address,destination_address,transfer.asset,transfer.amount,transfer.timestamp,hop,now,UUID(result.trace_id))
                    for item in result.evidence:
                        await conn.execute("INSERT INTO evidence(evidence_id,case_id,evidence_type,chain,tx_hash,source,captured_at,metadata,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (case_id,chain,tx_hash,evidence_type) DO NOTHING",UUID(item.evidence_id),case_uuid,item.type,item.chain,item.tx_hash,item.source,item.captured_at,json.dumps(item.metadata),now)
        except asyncpg.PostgresError as exc: raise DatabaseError("Trace persistence failed") from exc
    def _trace_from_rows(self, case_id, wallet_rows, edge_rows, evidence_rows, trace_id="", acquisition=None, trace_mode=DataMode.HISTORICAL, trace_provider="Persisted provider observation"):
        nodes={}; edges=[]
        evidence_by_tx={str(e["tx_hash"]).lower():str(e["evidence_id"]) for e in evidence_rows if e["tx_hash"]}
        for row in edge_rows:
            nodes.setdefault(row["source_wallet"],GraphNode(id=row["source_wallet"],address=row["source_wallet"],chain=row["chain"],depth=row["hop"]))
            nodes.setdefault(row["destination_wallet"],GraphNode(id=row["destination_wallet"],address=row["destination_wallet"],chain=row["chain"],depth=row["hop"]+1))
            raw=row["raw_reference"] or {}; raw=json.loads(raw) if isinstance(raw,str) else raw
            transfer_raw=row["transfer_raw_reference"] or raw
            transfer_raw=json.loads(transfer_raw) if isinstance(transfer_raw,str) else transfer_raw
            labels=transfer_raw.get("node_labels", {})
            types=transfer_raw.get("node_types", {})
            for address in (row["source_wallet"], row["destination_wallet"]):
                if address in nodes:
                    node=nodes[address]
                    node.metadata.update({"label": labels.get(address, node.metadata.get("label", "")), "entity_type": types.get(address, node.node_type), "is_root": address.lower()==str(row["source_wallet"]).lower() and node.depth==0, "is_endpoint": types.get(address)=="VASP"})
                    if types.get(address): node.node_type=types[address]; node.entity_type=types[address]
                    node.is_endpoint = types.get(address)=="VASP"
                    node.is_root = node.depth == 0
                    node.entity_name = "Demo Mixer Service" if node.node_type=="MIXER" else ("Demo Exchange" if node.node_type=="VASP" else None)
            transfer=Transfer(tx_hash=row["tx_hash"],chain=row["chain"],block_number=row["block_number"],timestamp=row["timestamp"],source=row["from_address"],destination=row["to_address"],asset=row["asset"],amount=row["amount"],value_native=float(row["native_value"]) if row["native_value"] is not None else None,provider=row["provider"] or raw.get("provider","PostgreSQL"),transfer_type=row["transfer_type"] or "native",contract_address=row["contract_address"] or None,token_id=row["token_id"] or None,decimals=row["decimals"],fee=str(row["fee"]) if row["fee"] is not None else None,raw_reference=transfer_raw)
            edges.append(GraphEdge(edge_id=f"{row['tx_hash']}:{row['source_wallet']}:{row['destination_wallet']}",source=row["source_wallet"],target=row["destination_wallet"],transfer=transfer,hop=row["hop"],evidence_id=evidence_by_tx.get(str(row["tx_hash"]).lower())))
        evidence=[Evidence(evidence_id=str(r["evidence_id"]),case_id=case_id,type=r["evidence_type"],chain=r["chain"],tx_hash=r["tx_hash"],source=r["source"],captured_at=r["captured_at"],metadata=(json.loads(r["metadata"]) if isinstance(r["metadata"],str) else (r["metadata"] or {})),content_hash=r.get("content_hash"),integrity_status=r.get("integrity_status") or "UNVERIFIED") for r in evidence_rows]
        reported = next((r["address"] for r in wallet_rows if str(r.get("role", "")).upper() == "REPORTED"), None)
        root = reported or next((r["address"] for r in wallet_rows), next(iter(nodes), ""))
        acq = AcquisitionStatistics(**self._json_dict(acquisition)) if acquisition else AcquisitionStatistics()
        metrics = TraceMetrics(node_count=len(nodes), edge_count=len(edges),
                               unique_wallet_count=len(nodes), maximum_hop=max((e.hop for e in edges), default=0),
                               path_count=1 if edges else 0,
                               unique_transaction_count=len({e.transaction_hash for e in edges}),
                               unique_asset_count=len({e.transfer.asset for e in edges}))
        ordered = sorted(edges, key=lambda edge: (edge.transfer.timestamp or datetime.min.replace(tzinfo=timezone.utc), edge.transaction_hash))
        path_nodes = [ordered[0].source] + [edge.target for edge in ordered] if ordered else [root]
        path = TransactionPath(path_id=f"persisted:{trace_id}", node_ids=path_nodes, edges=ordered) if ordered else None
        predominant = (acquisition or {}).get("predominant_path", []) if isinstance(acquisition, dict) else []
        # Persisted fixture metadata is authoritative; legacy traces retain their
        # historical ordered path for compatibility.
        return TraceResult(case_id=case_id,trace_id=trace_id,root_address=root,mode=trace_mode,provider=trace_provider,nodes=list(nodes.values()),edges=edges,signals=[],evidence=evidence,paths=[path] if path else [],metrics=metrics,acquisition=acq,predominant_path=predominant or path_nodes,limitations=["Persisted trace results do not re-run analytical rules on read."])

    async def list_traces(self, case_id: str) -> list[TraceResult]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM trace_runs WHERE case_id=$1 ORDER BY completed_at DESC",UUID(case_id))
            return [TraceResult(case_id=case_id,trace_id=str(r["trace_id"]),root_address=r["root_wallet"],mode=r["mode"],provider=r["provider"],nodes=[],edges=[],signals=[],evidence=[],status=r["status"],direction=r["direction"],limits=TraceLimits(**(r["limits"] or {})),metrics=TraceMetrics(node_count=r["node_count"],edge_count=r["edge_count"],unique_transaction_count=r["transaction_count"]),acquisition=AcquisitionStatistics(**self._json_dict(r["acquisition"])),limitations=["Use the trace detail endpoint to reconstruct persisted graph edges."]) for r in rows]
        except (ValueError,asyncpg.PostgresError) as exc:
            if isinstance(exc,ValueError): return []
            raise DatabaseError("Trace runs could not be retrieved") from exc

    async def get_trace(self, case_id: str, trace_id: str) -> TraceResult | None:
        # Case retrieval remains the canonical graph reconstruction path. The
        # detail endpoint currently exposes the latest persisted run.
        case=await self.get(case_id)
        return case.latest_trace if case and case.latest_trace and case.latest_trace.trace_id==trace_id else None

    async def attribution_catalog(self):
        pool=self._require_pool()
        async with pool.acquire() as conn:
            entity_rows=await conn.fetch("SELECT * FROM entities ORDER BY name")
            source_rows=await conn.fetch("SELECT * FROM attribution_sources ORDER BY name")
            attribution_rows=await conn.fetch("SELECT * FROM address_attributions")
            wallet_rows=await conn.fetch("SELECT address FROM wallets")
        entities=[Entity(entity_id=str(r["entity_id"]),name=r["name"],entity_type=r["entity_type"],legal_name=r["legal_name"],jurisdiction=r["jurisdiction"],website=r["website"],metadata=self._json_dict(r["metadata"])) for r in entity_rows]
        sources=[AttributionSource(source_id=str(r["source_id"]),name=r["name"],source_type=r["source_type"],publisher=r["publisher"],reference=r["reference"],reliability_level=r["reliability_level"],description=r["description"],dataset_version=r.get("dataset_version")) for r in source_rows]
        records=[AddressAttribution(attribution_id=str(r["attribution_id"]),chain=r["chain"],address=r["address"],entity_id=str(r["entity_id"]),role=r["role"],confidence=r["confidence"],source_id=str(r["source_id"]),source_reference=r["source_reference"],evidence_id=str(r["evidence_id"]) if r["evidence_id"] else None,first_seen=r["first_seen"],last_verified=r["last_verified"],metadata=self._json_dict(r["metadata"])) for r in attribution_rows]

        # In development mode, merge only the static, source-labelled synthetic
        # registry. Never derive an attribution from a wallet address.
        from .config import settings
        if settings.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE":
            from .synthetic_attribution import merge
            entities, sources, records = merge(entities, sources, records)

        return entities,sources,records


    async def entity_attributions(self, entity_id: str) -> list[AddressAttribution]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM address_attributions WHERE entity_id=$1 ORDER BY chain,address",UUID(entity_id))
            return [AddressAttribution(attribution_id=str(r["attribution_id"]),chain=r["chain"],address=r["address"],entity_id=str(r["entity_id"]),role=r["role"],confidence=r["confidence"],source_id=str(r["source_id"]),source_reference=r["source_reference"],evidence_id=str(r["evidence_id"]) if r["evidence_id"] else None,first_seen=r["first_seen"],last_verified=r["last_verified"],metadata=r["metadata"] or {}) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Entity attribution records could not be retrieved") from exc

    async def attribution_sources(self) -> list[AttributionSource]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM attribution_sources ORDER BY name")
            return [AttributionSource(source_id=str(r["source_id"]),name=r["name"],source_type=r["source_type"],publisher=r["publisher"],reference=r["reference"],reliability_level=r["reliability_level"],description=r["description"],dataset_version=r.get("dataset_version")) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Attribution sources could not be retrieved") from exc

    async def case_entities(self, case_id: str) -> list[Entity]:
        """Entities whose attributed addresses appear in this case's persisted graph."""
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("""SELECT DISTINCT e.* FROM entities e JOIN address_attributions aa ON aa.entity_id=e.entity_id
                    JOIN graph_edges ge ON lower(aa.address)=lower(ge.source_wallet) OR lower(aa.address)=lower(ge.destination_wallet)
                    WHERE ge.case_id=$1 ORDER BY e.name""", UUID(case_id))
            return [Entity(entity_id=str(r['entity_id']),name=r['name'],entity_type=r['entity_type'],legal_name=r['legal_name'],jurisdiction=r['jurisdiction'],website=r['website'],metadata=self._json_dict(r['metadata'])) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Case entities could not be retrieved") from exc

    async def wallet_entities(self, wallet_id: str) -> list[Entity]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("""SELECT DISTINCT e.* FROM wallets w JOIN address_attributions aa ON aa.chain=w.chain AND lower(aa.address)=lower(w.address)
                    JOIN entities e ON e.entity_id=aa.entity_id WHERE w.wallet_id=$1 ORDER BY e.name""", UUID(wallet_id))
            return [Entity(entity_id=str(r['entity_id']),name=r['name'],entity_type=r['entity_type'],legal_name=r['legal_name'],jurisdiction=r['jurisdiction'],website=r['website'],metadata=self._json_dict(r['metadata'])) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Wallet entities could not be retrieved") from exc

    async def graph_layout(self, case_id: str) -> GraphLayout:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("SELECT node_positions,viewport,updated_at FROM case_graph_layouts WHERE case_id=$1", UUID(case_id))
            positions=row['node_positions'] if row else {}
            viewport=row['viewport'] if row else {}
            positions=json.loads(positions) if isinstance(positions,str) else (positions or {})
            viewport=json.loads(viewport) if isinstance(viewport,str) else (viewport or {})
            return GraphLayout(case_id=case_id,node_positions=positions,viewport=viewport,updated_at=row['updated_at'] if row else None)
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Graph layout could not be retrieved") from exc

    async def save_graph_layout(self, case_id: str, layout: GraphLayoutUpdate) -> GraphLayout:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("""INSERT INTO case_graph_layouts(case_id,node_positions,viewport,updated_at) VALUES($1,$2::jsonb,$3::jsonb,now())
                    ON CONFLICT(case_id) DO UPDATE SET node_positions=EXCLUDED.node_positions,viewport=EXCLUDED.viewport,updated_at=now()
                    RETURNING node_positions,viewport,updated_at""", UUID(case_id),json.dumps(layout.node_positions),json.dumps(layout.viewport))
            positions=json.loads(row['node_positions']) if isinstance(row['node_positions'],str) else (row['node_positions'] or {})
            viewport=json.loads(row['viewport']) if isinstance(row['viewport'],str) else (row['viewport'] or {})
            return GraphLayout(case_id=case_id,node_positions=positions,viewport=viewport,updated_at=row['updated_at'])
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Graph layout could not be saved") from exc

    async def persist_patterns(self, observations: list[PatternObservation]) -> list[PatternObservation]:
        pool=self._require_pool(); now=datetime.now(timezone.utc); persisted=[]
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for item in observations:
                        await conn.execute("""INSERT INTO pattern_observations
                          (pattern_id,case_id,trace_id,pattern_type,status,confidence_level,confidence_score,severity,description,explanation,first_observed_at,last_observed_at,metadata,fingerprint,created_at,updated_at)
                          VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$15)
                          ON CONFLICT (fingerprint) DO NOTHING""",
                          UUID(item.pattern_id),UUID(item.case_id),UUID(item.trace_id),item.pattern_type,item.status,item.confidence_level,item.confidence_score,item.severity,item.description,item.explanation,item.first_observed_at,item.last_observed_at,json.dumps(item.metadata),item.fingerprint,now)
                        row=await conn.fetchrow("SELECT pattern_id FROM pattern_observations WHERE fingerprint=$1",item.fingerprint)
                        if not row: continue
                        for evidence_id in item.evidence_ids:
                            try: await conn.execute("INSERT INTO pattern_observation_evidence(pattern_id,evidence_id) VALUES($1,$2) ON CONFLICT DO NOTHING",row["pattern_id"],UUID(evidence_id))
                            except ValueError: continue
                        persisted.append(item.model_copy(update={"pattern_id":str(row["pattern_id"])}))
            return persisted
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Pattern observations could not be persisted") from exc

    def _pattern_from_row(self, row, evidence_ids: list[str] | None = None, transaction_hashes: list[str] | None = None) -> PatternObservation:
        metadata=row["metadata"] or {}
        if isinstance(metadata,str): metadata=json.loads(metadata)
        return PatternObservation(pattern_id=str(row["pattern_id"]),case_id=str(row["case_id"]),trace_id=str(row["trace_id"]),pattern_type=row["pattern_type"],status=row["status"],confidence_level=row["confidence_level"],confidence_score=float(row["confidence_score"]) if row["confidence_score"] is not None else None,severity=row["severity"],description=row["description"],explanation=row["explanation"],observed_at=row["last_observed_at"] or row["first_observed_at"] or row["created_at"],first_observed_at=row["first_observed_at"],last_observed_at=row["last_observed_at"],transaction_hashes=transaction_hashes or [],evidence_ids=evidence_ids or [],metadata=metadata,fingerprint=row["fingerprint"])

    async def list_patterns(self, case_id: str, trace_id: str | None = None) -> list[PatternObservation]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM pattern_observations WHERE case_id=$1 AND ($2::uuid IS NULL OR trace_id=$2) ORDER BY created_at DESC",UUID(case_id),UUID(trace_id) if trace_id else None)
                result=[]
                for row in rows:
                    evidence=await conn.fetch("SELECT e.evidence_id,e.tx_hash FROM pattern_observation_evidence poe JOIN evidence e ON e.evidence_id=poe.evidence_id WHERE poe.pattern_id=$1",row["pattern_id"])
                    result.append(self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence],[e["tx_hash"] for e in evidence if e["tx_hash"]]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Pattern observations could not be retrieved") from exc

    async def list_patterns_by_trace(self, trace_id: str) -> list[PatternObservation]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM pattern_observations WHERE trace_id=$1 ORDER BY created_at DESC",UUID(trace_id))
                result=[]
                for row in rows:
                    evidence=await conn.fetch("SELECT e.evidence_id,e.tx_hash FROM pattern_observation_evidence poe JOIN evidence e ON e.evidence_id=poe.evidence_id WHERE poe.pattern_id=$1",row["pattern_id"])
                    result.append(self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence],[e["tx_hash"] for e in evidence if e["tx_hash"]]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Trace pattern observations could not be retrieved") from exc

    async def get_pattern(self, case_id: str, pattern_id: str) -> PatternObservation | None:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("SELECT * FROM pattern_observations WHERE case_id=$1 AND pattern_id=$2",UUID(case_id),UUID(pattern_id))
                if not row: return None
                evidence=await conn.fetch("SELECT e.evidence_id,e.tx_hash FROM pattern_observation_evidence poe JOIN evidence e ON e.evidence_id=poe.evidence_id WHERE poe.pattern_id=$1",UUID(pattern_id))
                return self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence],[e["tx_hash"] for e in evidence if e["tx_hash"]])
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Pattern observation could not be retrieved") from exc

    async def pattern_summary(self, case_id: str, trace_id: str | None = None) -> PatternSummary:
        rows=await self.list_patterns(case_id,trace_id); summary=PatternSummary(total_patterns=len(rows))
        for item in rows:
            summary.by_type[item.pattern_type]=summary.by_type.get(item.pattern_type,0)+1
            summary.by_severity[item.severity]=summary.by_severity.get(item.severity,0)+1
            summary.by_confidence[item.confidence_level]=summary.by_confidence.get(item.confidence_level,0)+1
            if item.severity=="CRITICAL": summary.critical_count+=1
            if item.severity=="HIGH": summary.high_count+=1
            if item.severity=="MEDIUM": summary.medium_count+=1
        return summary

    async def save_workflow_state(self, case_id: str, state: InvestigationWorkflowState) -> InvestigationWorkflowState:
        if not hasattr(self, "_in_mem_workflows"): self._in_mem_workflows = {}
        self._in_mem_workflows[case_id] = state
        return state

    async def get_workflow_state(self, case_id: str) -> InvestigationWorkflowState | None:
        if not hasattr(self, "_in_mem_workflows"): self._in_mem_workflows = {}
        return self._in_mem_workflows.get(case_id)

    async def update_workflow_stage(self, case_id: str, stage: str, stage_detail: WorkflowStageDetail) -> InvestigationWorkflowState:
        if not hasattr(self, "_in_mem_workflows"): self._in_mem_workflows = {}
        state = self._in_mem_workflows.get(case_id)
        if not state:
            state = InvestigationWorkflowState(case_id=case_id, started_at=datetime.now(timezone.utc), stages=[])
        updated_stages = []
        replaced = False
        for s in state.stages:
            if s.stage == stage_detail.stage:
                updated_stages.append(stage_detail)
                replaced = True
            else:
                updated_stages.append(s)
        if not replaced:
            updated_stages.append(stage_detail)
        state.stages = updated_stages
        state.current_stage = stage_detail.stage
        self._in_mem_workflows[case_id] = state
        return state

    async def reset_realtime_event(self, event_id: str) -> RealtimeEvent:
        event = await self.get_realtime_event(event_id)
        if not event: raise DatabaseError(f"Realtime event {event_id} not found")
        return event.model_copy(update={"processing_status": RealtimeProcessingStatus.RECEIVED, "error": None})

    async def risk_registry_search(self, query: str = "", wallet: str | None = None) -> list:
        return []


