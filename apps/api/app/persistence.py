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
                rows=await conn.fetch("""SELECT c.case_id,c.title,c.fraud_type,c.priority,c.status,c.created_at,c.updated_at,
                    (SELECT count(*) FROM case_wallets cw WHERE cw.case_id=c.case_id) AS wallet_count,
                    (SELECT count(*) FROM case_transactions ct WHERE ct.case_id=c.case_id) AS transaction_count, c.workflow_stage
                    FROM cases c ORDER BY c.updated_at DESC""")
            return [CaseListItem(case_id=str(r["case_id"]),title=r["title"],fraud_type=r["fraud_type"],priority=r["priority"],status=r["status"],created_at=r["created_at"],updated_at=r["updated_at"],wallet_count=r["wallet_count"],transaction_count=r["transaction_count"],workflow_stage=r["workflow_stage"]) for r in rows]
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
                    (SELECT GREATEST(COALESCE((SELECT max(timestamp) FROM investigation_timeline), 'epoch'::timestamptz), COALESCE((SELECT max(timestamp) FROM transactions), 'epoch'::timestamptz))) AS last_activity_at""")
            last=row["last_activity_at"]
            return DashboardSummary(active_cases=row["active_cases"],wallets_under_review=row["wallets_under_review"],high_priority_alerts=row["high_priority_alerts"],attributed_entities=row["attributed_entities"],observed_transactions=row["observed_transactions"],active_watches=row["active_watches"],last_activity_at=None if last and last.year==1970 else last)
        except asyncpg.PostgresError as exc: raise DatabaseError("Dashboard summary could not be retrieved") from exc

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
                latest_trace_id=await conn.fetchval("SELECT trace_id FROM trace_runs WHERE case_id=$1 ORDER BY completed_at DESC LIMIT 1",case_uuid)
                edge_rows=await conn.fetch("SELECT ge.*,t.chain,t.tx_hash,t.block_number,t.timestamp,t.from_address,t.to_address,t.native_value,t.fee,t.raw_reference,tt.transfer_type,tt.contract_address,tt.token_id,tt.decimals,tt.raw_reference AS transfer_raw_reference FROM graph_edges ge JOIN transactions t ON t.transaction_id=ge.transaction_id LEFT JOIN transaction_transfers tt ON tt.transaction_id=ge.transaction_id AND tt.source_address=ge.source_wallet AND tt.destination_address=ge.destination_wallet AND tt.asset=ge.asset AND tt.amount=ge.amount WHERE ge.case_id=$1 AND ($2::uuid IS NULL OR ge.trace_id=$2) ORDER BY ge.created_at",case_uuid,latest_trace_id)
                evidence_rows=await conn.fetch("SELECT * FROM evidence WHERE case_id=$1 ORDER BY created_at",case_uuid)
            latest_trace=self._trace_from_rows(str(case_uuid),wallet_rows,edge_rows,evidence_rows,str(latest_trace_id) if latest_trace_id else "") if edge_rows or evidence_rows else None
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
                    await conn.execute("INSERT INTO trace_runs(trace_id,case_id,root_wallet,chain,direction,started_at,completed_at,status,limits,node_count,edge_count,transaction_count,provider,mode) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",UUID(result.trace_id),case_uuid,result.root_address,result.edges[0].transfer.chain if result.edges else Chain.ETHEREUM,result.direction,now,now,result.status,json.dumps(result.limits.model_dump() if result.limits else {}),result.metrics.node_count,result.metrics.edge_count,result.metrics.unique_transaction_count,result.provider,result.mode)
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
    def _trace_from_rows(self, case_id, wallet_rows, edge_rows, evidence_rows, trace_id=""):
        nodes={}; edges=[]
        for row in edge_rows:
            nodes.setdefault(row["source_wallet"],GraphNode(id=row["source_wallet"],address=row["source_wallet"],depth=row["hop"]))
            nodes.setdefault(row["destination_wallet"],GraphNode(id=row["destination_wallet"],address=row["destination_wallet"],depth=row["hop"]+1))
            raw=row["raw_reference"] or {}; raw=json.loads(raw) if isinstance(raw,str) else raw
            transfer_raw=row["transfer_raw_reference"] or raw
            transfer_raw=json.loads(transfer_raw) if isinstance(transfer_raw,str) else transfer_raw
            transfer=Transfer(tx_hash=row["tx_hash"],chain=row["chain"],block_number=row["block_number"],timestamp=row["timestamp"],source=row["from_address"],destination=row["to_address"],asset=row["asset"],amount=row["amount"],value_native=float(row["native_value"]) if row["native_value"] is not None else None,provider=raw.get("provider","PostgreSQL"),transfer_type=row["transfer_type"] or "native",contract_address=row["contract_address"] or None,token_id=row["token_id"] or None,decimals=row["decimals"],raw_reference=transfer_raw)
            edges.append(GraphEdge(source=row["source_wallet"],target=row["destination_wallet"],transfer=transfer))
        evidence=[Evidence(evidence_id=str(r["evidence_id"]),case_id=case_id,type=r["evidence_type"],chain=r["chain"],tx_hash=r["tx_hash"],source=r["source"],captured_at=r["captured_at"],metadata=(json.loads(r["metadata"]) if isinstance(r["metadata"],str) else (r["metadata"] or {})),content_hash=r.get("content_hash"),integrity_status=r.get("integrity_status") or "UNVERIFIED") for r in evidence_rows]
        root=next(iter(nodes),next((r["address"] for r in wallet_rows),""))
        return TraceResult(case_id=case_id,trace_id=trace_id,root_address=root,mode=DataMode.HISTORICAL,provider="Persisted provider observation",nodes=list(nodes.values()),edges=edges,signals=[],evidence=evidence,metrics=TraceMetrics(node_count=len(nodes),edge_count=len(edges),unique_transaction_count=len({e.transaction_hash for e in edges}),unique_asset_count=len({e.transfer.asset for e in edges})),limitations=["Persisted trace results do not re-run analytical rules on read."])

    async def list_traces(self, case_id: str) -> list[TraceResult]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM trace_runs WHERE case_id=$1 ORDER BY completed_at DESC",UUID(case_id))
            return [TraceResult(case_id=case_id,trace_id=str(r["trace_id"]),root_address=r["root_wallet"],mode=r["mode"],provider=r["provider"],nodes=[],edges=[],signals=[],evidence=[],status=r["status"],direction=r["direction"],limits=TraceLimits(**(r["limits"] or {})),metrics=TraceMetrics(node_count=r["node_count"],edge_count=r["edge_count"],unique_transaction_count=r["transaction_count"]),limitations=["Use the trace detail endpoint to reconstruct persisted graph edges."]) for r in rows]
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
        entities=[Entity(entity_id=str(r["entity_id"]),name=r["name"],entity_type=r["entity_type"],legal_name=r["legal_name"],jurisdiction=r["jurisdiction"],website=r["website"],metadata=r["metadata"] or {}) for r in entity_rows]
        sources=[AttributionSource(source_id=str(r["source_id"]),name=r["name"],source_type=r["source_type"],publisher=r["publisher"],reference=r["reference"],reliability_level=r["reliability_level"],description=r["description"],dataset_version=r.get("dataset_version")) for r in source_rows]
        records=[AddressAttribution(attribution_id=str(r["attribution_id"]),chain=r["chain"],address=r["address"],entity_id=str(r["entity_id"]),role=r["role"],confidence=r["confidence"],source_id=str(r["source_id"]),source_reference=r["source_reference"],evidence_id=str(r["evidence_id"]) if r["evidence_id"] else None,first_seen=r["first_seen"],last_verified=r["last_verified"],metadata=r["metadata"] or {}) for r in attribution_rows]
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

    def _pattern_from_row(self, row, evidence_ids: list[str] | None = None) -> PatternObservation:
        metadata=row["metadata"] or {}
        if isinstance(metadata,str): metadata=json.loads(metadata)
        return PatternObservation(pattern_id=str(row["pattern_id"]),case_id=str(row["case_id"]),trace_id=str(row["trace_id"]),pattern_type=row["pattern_type"],status=row["status"],confidence_level=row["confidence_level"],confidence_score=float(row["confidence_score"]) if row["confidence_score"] is not None else None,severity=row["severity"],description=row["description"],explanation=row["explanation"],observed_at=row["last_observed_at"] or row["first_observed_at"] or row["created_at"],first_observed_at=row["first_observed_at"],last_observed_at=row["last_observed_at"],evidence_ids=evidence_ids or [],metadata=metadata,fingerprint=row["fingerprint"])

    async def list_patterns(self, case_id: str, trace_id: str | None = None) -> list[PatternObservation]:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM pattern_observations WHERE case_id=$1 AND ($2::uuid IS NULL OR trace_id=$2) ORDER BY created_at DESC",UUID(case_id),UUID(trace_id) if trace_id else None)
                result=[]
                for row in rows:
                    evidence=await conn.fetch("SELECT evidence_id FROM pattern_observation_evidence WHERE pattern_id=$1",row["pattern_id"])
                    result.append(self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence]))
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
                    evidence=await conn.fetch("SELECT evidence_id FROM pattern_observation_evidence WHERE pattern_id=$1",row["pattern_id"])
                    result.append(self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Trace pattern observations could not be retrieved") from exc

    async def get_pattern(self, case_id: str, pattern_id: str) -> PatternObservation | None:
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                row=await conn.fetchrow("SELECT * FROM pattern_observations WHERE case_id=$1 AND pattern_id=$2",UUID(case_id),UUID(pattern_id))
                if not row: return None
                evidence=await conn.fetch("SELECT evidence_id FROM pattern_observation_evidence WHERE pattern_id=$1",UUID(pattern_id))
                return self._pattern_from_row(row,[str(e["evidence_id"]) for e in evidence])
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
