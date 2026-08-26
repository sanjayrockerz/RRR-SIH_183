from datetime import datetime, timezone
from uuid import UUID, uuid4
import json
import asyncpg

from .domain import *

class RiskPersistenceMixin:
    async def append_audit_event(self, event: AuditEvent) -> None:
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO audit_events(event_id,case_id,action,resource_type,resource_id,actor_id,occurred_at,metadata) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",UUID(event.event_id),UUID(event.case_id) if event.case_id else None,event.action,event.resource_type,event.resource_id,event.actor_id,event.occurred_at,json.dumps(event.metadata))
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Audit event could not be persisted") from exc

    async def persist_risk(self, assessment: RiskAssessment, alerts: list[RiskAlertCandidate]) -> RiskAssessment:
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1 FOR UPDATE",UUID(assessment.case_id)):
                        raise DatabaseError("Case not found")
                    previous=await conn.fetchrow("SELECT assessment_id,version FROM risk_assessments WHERE case_id=$1 AND subject_id=$2 ORDER BY version DESC LIMIT 1",UUID(assessment.case_id),assessment.subject.subject_id)
                    version=(int(previous["version"])+1) if previous else assessment.version
                    previous_id=previous["assessment_id"] if previous else (UUID(assessment.previous_assessment_id) if assessment.previous_assessment_id else None)
                    assessment=assessment.model_copy(update={"version":version,"previous_assessment_id":str(previous_id) if previous_id else None})
                    await conn.execute("""INSERT INTO risk_assessments
                      (assessment_id,case_id,trace_id,subject_id,subject_chain,subject_address,subject_type,version,score,risk_band,investigative_priority,priority_reason,watch_status,calculation_version,calculated_at,explanation,previous_assessment_id,previous_score,score_delta,delta_metadata)
                      VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)""",
                      UUID(assessment.assessment_id),UUID(assessment.case_id),UUID(assessment.trace_id),assessment.subject.subject_id,assessment.subject.chain,assessment.subject.address,assessment.subject.subject_type,assessment.version,assessment.score,assessment.band,assessment.priority,assessment.priority_reason,assessment.watch_status,assessment.calculation_version,assessment.calculated_at,assessment.explanation,previous_id,assessment.delta.previous_score if assessment.delta else None,assessment.delta.delta if assessment.delta else None,json.dumps(assessment.delta.model_dump() if assessment.delta else {}))
                    for factor in assessment.factors:
                        await conn.execute("""INSERT INTO risk_factors(factor_id,assessment_id,definition_id,name,category,contribution,max_contribution,explanation,confidence_level,metadata)
                          VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT(assessment_id,definition_id) DO NOTHING""",UUID(factor.factor_id),UUID(assessment.assessment_id),factor.definition_id,factor.name,factor.category,factor.contribution,factor.max_contribution,factor.explanation,factor.confidence_level,json.dumps(factor.metadata))
                        for evidence_id in factor.evidence_ids:
                            try: await conn.execute("INSERT INTO risk_factor_evidence(factor_id,evidence_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(factor.factor_id),UUID(evidence_id))
                            except ValueError: continue
                        for pattern_id in factor.pattern_ids:
                            try: await conn.execute("INSERT INTO risk_assessment_patterns(assessment_id,pattern_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(assessment.assessment_id),UUID(pattern_id))
                            except ValueError: continue
                            try: await conn.execute("INSERT INTO risk_factor_patterns(factor_id,pattern_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(factor.factor_id),UUID(pattern_id))
                            except ValueError: continue
                        for entity_id in factor.entity_ids:
                            try: await conn.execute("INSERT INTO risk_assessment_entities(assessment_id,entity_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(assessment.assessment_id),UUID(entity_id))
                            except ValueError: continue
                            try: await conn.execute("INSERT INTO risk_factor_entities(factor_id,entity_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(factor.factor_id),UUID(entity_id))
                            except ValueError: continue
                        for tx_hash in factor.transaction_hashes:
                            await conn.execute("INSERT INTO risk_assessment_transactions(assessment_id,transaction_hash) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(assessment.assessment_id),tx_hash)
                            await conn.execute("INSERT INTO risk_factor_transactions(factor_id,transaction_hash) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(factor.factor_id),tx_hash)
                    for alert in alerts:
                        await conn.execute("INSERT INTO risk_alert_candidates(candidate_id,case_id,subject_id,assessment_id,trigger,severity,risk_delta,pattern_ids,evidence_ids,status,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",UUID(alert.candidate_id),UUID(alert.case_id),alert.subject_id,UUID(alert.assessment_id),alert.trigger,alert.severity,alert.risk_delta,json.dumps(alert.pattern_ids),json.dumps(alert.evidence_ids),alert.status,alert.created_at)
            return await self._load_risk(assessment.case_id,assessment.assessment_id)
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Risk assessment could not be persisted") from exc

    async def _load_risk(self, case_id: str, assessment_id: str):
        pool=self._require_pool()
        async with pool.acquire() as conn:
            row=await conn.fetchrow("SELECT * FROM risk_assessments WHERE case_id=$1 AND assessment_id=$2",UUID(case_id),UUID(assessment_id))
            if not row: return None
            factors=await self._load_risk_factors(conn,row["assessment_id"])
            metadata=row["delta_metadata"] or {}
            if isinstance(metadata,str): metadata=json.loads(metadata)
            delta=RiskDelta(**metadata) if metadata else None
            return RiskAssessment(assessment_id=str(row["assessment_id"]),case_id=str(row["case_id"]),trace_id=str(row["trace_id"]),subject=RiskSubject(subject_id=row["subject_id"],case_id=str(row["case_id"]),chain=row["subject_chain"],address=row["subject_address"],subject_type=row["subject_type"]),version=row["version"],score=float(row["score"]),band=row["risk_band"],priority=row["investigative_priority"],priority_reason=row["priority_reason"],watch_status=row["watch_status"],factors=factors,delta=delta,calculation_version=row["calculation_version"],calculated_at=row["calculated_at"],evidence_ids=list(dict.fromkeys(e for f in factors for e in f.evidence_ids)),pattern_ids=list(dict.fromkeys(p for f in factors for p in f.pattern_ids)),entity_ids=list(dict.fromkeys(e for f in factors for e in f.entity_ids)),explanation=row["explanation"],previous_assessment_id=str(row["previous_assessment_id"]) if row["previous_assessment_id"] else None)

    async def _load_risk_factors(self, conn, assessment_id):
        rows=await conn.fetch("SELECT * FROM risk_factors WHERE assessment_id=$1 ORDER BY category,definition_id",assessment_id); result=[]
        for row in rows:
            evidence=await conn.fetch("SELECT evidence_id FROM risk_factor_evidence WHERE factor_id=$1",row["factor_id"])
            pattern_rows=await conn.fetch("SELECT pattern_id FROM risk_factor_patterns WHERE factor_id=$1",row["factor_id"])
            entity_rows=await conn.fetch("SELECT entity_id FROM risk_factor_entities WHERE factor_id=$1",row["factor_id"])
            tx_rows=await conn.fetch("SELECT transaction_hash FROM risk_factor_transactions WHERE factor_id=$1",row["factor_id"])
            metadata=row["metadata"] or {}
            if isinstance(metadata,str): metadata=json.loads(metadata)
            result.append(RiskFactor(factor_id=str(row["factor_id"]),definition_id=row["definition_id"],name=row["name"],category=row["category"],contribution=float(row["contribution"]),max_contribution=float(row["max_contribution"]),explanation=row["explanation"],confidence_level=row["confidence_level"],pattern_ids=[str(x["pattern_id"]) for x in pattern_rows],entity_ids=[str(x["entity_id"]) for x in entity_rows],transaction_hashes=[x["transaction_hash"] for x in tx_rows],evidence_ids=[str(x["evidence_id"]) for x in evidence],metadata=metadata))
        return result

    async def _risk_rows(self, case_id: str, subject_id: str | None = None):
        pool=self._require_pool()
        async with pool.acquire() as conn:
            rows=await conn.fetch("SELECT assessment_id FROM risk_assessments WHERE case_id=$1 AND ($2::text IS NULL OR subject_id=$2) ORDER BY version DESC",UUID(case_id),subject_id)
        return [item for item in [await self._load_risk(case_id,str(row["assessment_id"])) for row in rows] if item]

    async def latest_risk(self, case_id: str, subject_id: str | None = None):
        rows=await self._risk_rows(case_id,subject_id); return rows[0] if rows else None
    async def risk_history(self, case_id: str, subject_id: str | None = None): return await self._risk_rows(case_id,subject_id)

    async def risk_by_trace(self, trace_id: str):
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn: rows=await conn.fetch("SELECT case_id,assessment_id FROM risk_assessments WHERE trace_id=$1 ORDER BY calculated_at DESC",UUID(trace_id))
            result=[]
            for row in rows:
                item=await self._load_risk(str(row["case_id"]),str(row["assessment_id"]))
                if item: result.append(item)
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Trace risk could not be retrieved") from exc

    async def risk_by_subject(self, subject_id: str):
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn: rows=await conn.fetch("SELECT case_id,assessment_id FROM risk_assessments WHERE subject_id=$1 ORDER BY calculated_at DESC",subject_id.lower())
            result=[]
            for row in rows:
                item=await self._load_risk(str(row["case_id"]),str(row["assessment_id"]))
                if item: result.append(item)
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Subject risk could not be retrieved") from exc

    async def risk_by_wallet(self, wallet_id: str):
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows=await conn.fetch("SELECT ra.case_id,ra.assessment_id FROM risk_assessments ra JOIN wallets w ON w.address=ra.subject_address AND w.chain=ra.subject_chain WHERE w.wallet_id=$1 ORDER BY ra.calculated_at DESC",UUID(wallet_id))
            result=[]
            for row in rows:
                item=await self._load_risk(str(row["case_id"]),str(row["assessment_id"]))
                if item: result.append(item)
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Wallet risk could not be retrieved") from exc

    async def risk_factors(self, case_id: str, assessment_id: str | None = None):
        assessment=await self.latest_risk(case_id) if not assessment_id else await self._load_risk(case_id,assessment_id)
        return assessment.factors if assessment else []

    async def risk_alerts(self, case_id: str, subject_id: str | None = None):
        from .persistence import DatabaseError
        pool=self._require_pool()
        try:
            async with pool.acquire() as conn: rows=await conn.fetch("SELECT * FROM risk_alert_candidates WHERE case_id=$1 AND ($2::text IS NULL OR subject_id=$2) ORDER BY created_at DESC",UUID(case_id),subject_id)
            result=[]
            for row in rows:
                result.append(RiskAlertCandidate(candidate_id=str(row["candidate_id"]),case_id=str(row["case_id"]),subject_id=row["subject_id"],assessment_id=str(row["assessment_id"]),trigger=row["trigger"],severity=row["severity"],risk_delta=float(row["risk_delta"]),pattern_ids=json.loads(row["pattern_ids"]) if isinstance(row["pattern_ids"],str) else (row["pattern_ids"] or []),evidence_ids=json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or []),created_at=row["created_at"],status=row["status"]))
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Risk alert candidates could not be retrieved") from exc
