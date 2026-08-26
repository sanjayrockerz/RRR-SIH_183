from datetime import datetime, timezone
from uuid import UUID, uuid4
import json
import asyncpg
from .config import settings
from .domain import *
from .services import CaseRepository
from .risk_persistence import RiskPersistenceMixin
from .realtime_persistence import RealtimePersistenceMixin
from .cross_chain_persistence import CrossChainPersistenceMixin

class DatabaseError(RuntimeError):
    """Database failures safe to translate at the HTTP boundary."""

class PostgresCaseRepository(CrossChainPersistenceMixin, RealtimePersistenceMixin, RiskPersistenceMixin, CaseRepository):
    def __init__(self): self.pool: asyncpg.Pool | None = None
    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(settings.database_url, min_size=settings.database_min_pool_size, max_size=settings.database_max_pool_size)
        except (OSError, asyncpg.PostgresError) as exc:
            raise DatabaseError("Database connection failed") from exc
    async def close(self):
        if self.pool: await self.pool.close()
    def _require_pool(self):
        if not self.pool: raise DatabaseError("Database is not connected")
        return self.pool
    async def create(self, data: CaseCreate) -> InvestigationCase:
        case_id=uuid4(); now=datetime.now(timezone.utc); pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO cases(case_id,title,fraud_type,status,priority,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6,$6)",case_id,data.title,data.fraud_type,"OPEN",data.priority,now)
            result=await self.get(str(case_id)); assert result; return result
        except asyncpg.PostgresError as exc: raise DatabaseError("Case could not be persisted") from exc
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
            return InvestigationCase(case_id=str(row["case_id"]),title=row["title"],fraud_type=row["fraud_type"],priority=row["priority"],status=row["status"],created_at=row["created_at"],updated_at=row["updated_at"],wallets=[WalletCreate(address=r["address"],chain=r["chain"]) for r in wallet_rows],transactions=[TransactionCreate(tx_hash=r["tx_hash"],chain=r["chain"]) for r in tx_rows],latest_trace=latest_trace)
        except ValueError: return None
        except asyncpg.PostgresError as exc: raise DatabaseError("Case could not be retrieved") from exc
    async def add_wallet(self, case_id: str, wallet: WalletCreate) -> InvestigationCase:
        pool=self._require_pool(); case_uuid=UUID(case_id); address=wallet.address.lower()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid): return None
                    existing=await conn.fetchval("SELECT wallet_id FROM wallets WHERE chain=$1 AND address=$2",wallet.chain,address)
                    if not existing: existing=await conn.fetchval("INSERT INTO wallets(wallet_id,chain,address,created_at) VALUES($1,$2,$3,$4) RETURNING wallet_id",uuid4(),wallet.chain,address,datetime.now(timezone.utc))
                    await conn.execute("INSERT INTO case_wallets(case_id,wallet_id,role,created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",case_uuid,existing,"REPORTED",datetime.now(timezone.utc))
            result=await self.get(case_id); assert result; return result
        except asyncpg.PostgresError as exc: raise DatabaseError("Wallet could not be persisted") from exc
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
                        hop=next((n.depth for n in result.nodes if n.address.lower()==edge.source.lower()),0)
                        await conn.execute("INSERT INTO graph_edges(edge_id,case_id,transaction_id,source_wallet,destination_wallet,asset,amount,timestamp,hop,created_at,trace_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING",uuid4(),case_uuid,tx_id,edge.source.lower(),edge.target.lower(),transfer.asset,transfer.amount,transfer.timestamp,hop,now,UUID(result.trace_id))
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
        evidence=[Evidence(evidence_id=str(r["evidence_id"]),case_id=case_id,type=r["evidence_type"],chain=r["chain"],tx_hash=r["tx_hash"],source=r["source"],captured_at=r["captured_at"],metadata=(json.loads(r["metadata"]) if isinstance(r["metadata"],str) else (r["metadata"] or {}))) for r in evidence_rows]
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
        sources=[AttributionSource(source_id=str(r["source_id"]),name=r["name"],source_type=r["source_type"],publisher=r["publisher"],reference=r["reference"],reliability_level=r["reliability_level"],description=r["description"]) for r in source_rows]
        records=[AddressAttribution(attribution_id=str(r["attribution_id"]),chain=r["chain"],address=r["address"],entity_id=str(r["entity_id"]),role=r["role"],confidence=r["confidence"],source_id=str(r["source_id"]),source_reference=r["source_reference"],evidence_id=str(r["evidence_id"]) if r["evidence_id"] else None,first_seen=r["first_seen"],last_verified=r["last_verified"],metadata=r["metadata"] or {}) for r in attribution_rows]
        return entities,sources,records

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
