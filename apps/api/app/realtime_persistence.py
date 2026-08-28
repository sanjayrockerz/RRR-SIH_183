from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import json
import asyncpg
from .domain import *

class RealtimePersistenceMixin:
    async def create_watch(self, watch: WatchTarget) -> WatchTarget:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                persisted_watch_id=await conn.fetchval("""INSERT INTO watch_targets(watch_id,case_id,chain,address,source,created_at,status,provider,subscription_id,expansion_policy,max_hops,max_new_nodes_per_event,max_new_edges_per_event,max_value,allowed_assets,error)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                ON CONFLICT(case_id,chain,address) DO UPDATE SET status=EXCLUDED.status,source=EXCLUDED.source,provider=EXCLUDED.provider,error=EXCLUDED.error
                RETURNING watch_id""",UUID(watch.watch_id),UUID(watch.case_id),watch.chain,watch.address.lower(),watch.source,watch.created_at,watch.status,watch.provider,watch.subscription_id,watch.expansion_policy,watch.max_hops,watch.max_new_nodes_per_event,watch.max_new_edges_per_event,watch.max_value,json.dumps(watch.allowed_assets),watch.error)
            return await self.get_watch(watch.case_id,str(persisted_watch_id))
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Watch could not be persisted") from exc

    def _watch_from_row(self,row):
        assets=row["allowed_assets"] or []
        if isinstance(assets,str): assets=json.loads(assets)
        return WatchTarget(watch_id=str(row["watch_id"]),case_id=str(row["case_id"]),address=row["address"],chain=row["chain"],source=row["source"],created_at=row["created_at"],status=row["status"],provider=row["provider"],subscription_id=row["subscription_id"],last_event_at=row["last_event_at"],last_processed_block=row["last_processed_block"],last_processed_event=row["last_processed_event"],expansion_policy=row["expansion_policy"],max_hops=row["max_hops"],max_new_nodes_per_event=row["max_new_nodes_per_event"],max_new_edges_per_event=row["max_new_edges_per_event"],max_value=float(row["max_value"]),allowed_assets=assets,error=row["error"])

    async def list_watches(self,case_id:str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM watch_targets WHERE case_id=$1 ORDER BY created_at",UUID(case_id))
            return [self._watch_from_row(row) for row in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Watches could not be retrieved") from exc

    async def list_all_watches(self, chain:Chain|None=None):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT * FROM watch_targets WHERE ($1::text IS NULL OR chain=$1) ORDER BY created_at",chain)
            return [self._watch_from_row(row) for row in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Watch targets could not be retrieved") from exc

    async def get_watch(self,case_id:str,watch_id:str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: row=await conn.fetchrow("SELECT * FROM watch_targets WHERE case_id=$1 AND watch_id=$2",UUID(case_id),UUID(watch_id))
            return self._watch_from_row(row) if row else None
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Watch could not be retrieved") from exc

    async def update_watch(self,watch:WatchTarget):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("UPDATE watch_targets SET status=$3,last_event_at=$4,last_processed_block=$5,last_processed_event=$6,subscription_id=$7,error=$8 WHERE case_id=$1 AND watch_id=$2",UUID(watch.case_id),UUID(watch.watch_id),watch.status,watch.last_event_at,watch.last_processed_block,watch.last_processed_event,watch.subscription_id,watch.error)
            return await self.get_watch(watch.case_id,watch.watch_id)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Watch could not be updated") from exc

    async def ingest_realtime_event(self,event:RealtimeEvent):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                inserted=await conn.fetchval("""INSERT INTO realtime_events(event_id,provider,provider_event_id,chain,event_type,received_at,observed_at,block_number,block_hash,transaction_hash,transfer_index,from_address,to_address,asset,amount,contract_address,token_id,raw_provider_reference,processing_status,confirmation_state,removed,error)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
                ON CONFLICT(event_id) DO NOTHING RETURNING event_id""",event.event_id,event.provider,event.provider_event_id,event.chain,event.event_type,event.received_at,event.observed_at,event.block_number,event.block_hash,event.transaction_hash,event.transfer_index,event.from_address,event.to_address,event.asset,event.amount,event.contract_address,event.token_id,json.dumps(event.raw_provider_reference),event.processing_status,event.confirmation_state,event.removed,event.error)
                duplicate=inserted is None
                row=await conn.fetchrow("SELECT * FROM realtime_events WHERE event_id=$1",event.event_id)
            if duplicate:
                event=self._event_from_row(row)
                # A retryable delivery may be submitted again by the provider;
                # an applied or dead-lettered event must remain idempotent.
                duplicate=event.processing_status not in {RealtimeProcessingStatus.RECEIVED, RealtimeProcessingStatus.RETRY_PENDING, RealtimeProcessingStatus.FAILED}
                if duplicate:
                    event=event.model_copy(update={"processing_status":RealtimeProcessingStatus.DUPLICATE})
            return event,duplicate
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime event could not be persisted") from exc

    def _event_from_row(self,row):
        raw=row["raw_provider_reference"] or {}
        if isinstance(raw,str): raw=json.loads(raw)
        return RealtimeEvent(event_id=row["event_id"],provider=row["provider"],provider_event_id=row["provider_event_id"],chain=row["chain"],event_type=row["event_type"],received_at=row["received_at"],observed_at=row["observed_at"],block_number=row["block_number"],block_hash=row["block_hash"],transaction_hash=row["transaction_hash"],transfer_index=row["transfer_index"],from_address=row["from_address"],to_address=row["to_address"],asset=row["asset"],amount=row["amount"],contract_address=row["contract_address"],token_id=row["token_id"],raw_provider_reference=raw,processing_status=row["processing_status"],confirmation_state=row["confirmation_state"],removed=row["removed"],error=row["error"],attempt_count=row["attempt_count"],next_attempt_at=row["next_attempt_at"],dead_lettered_at=row["dead_lettered_at"])

    async def apply_realtime_event(self,event:RealtimeEvent,watch:WatchTarget):
        from .persistence import DatabaseError
        now=datetime.now(timezone.utc)
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    if await conn.fetchval("SELECT 1 FROM realtime_event_applications WHERE event_id=$1 AND case_id=$2",event.event_id,UUID(watch.case_id)):
                        return RealtimeApplicationResult(event=event,case_id=watch.case_id,watch_id=watch.watch_id,duplicate=True)
                    if event.removed or event.event_type == RealtimeEventType.REORG:
                        await conn.execute("UPDATE realtime_events SET processing_status='APPLIED',confirmation_state='REORGED',error=$2 WHERE event_id=$1",event.event_id,"Provider marked this observation as removed; no new graph edge was created")
                        return RealtimeApplicationResult(event=event.model_copy(update={"processing_status":RealtimeProcessingStatus.APPLIED,"confirmation_state":ConfirmationState.REORGED}),case_id=watch.case_id,watch_id=watch.watch_id)
                    trace_id=await conn.fetchval("SELECT trace_id FROM trace_runs WHERE case_id=$1 ORDER BY completed_at DESC LIMIT 1",UUID(watch.case_id))
                    known_destination=await conn.fetchval("SELECT 1 FROM graph_edges WHERE case_id=$1 AND (source_wallet=$2 OR destination_wallet=$2) LIMIT 1",UUID(watch.case_id),event.to_address)
                    tx_id=await conn.fetchval("SELECT transaction_id FROM transactions WHERE chain=$1 AND tx_hash=$2",event.chain,event.transaction_hash.lower())
                    if not tx_id:
                        tx_id=await conn.fetchval("""INSERT INTO transactions(transaction_id,chain,tx_hash,block_number,timestamp,status,from_address,to_address,native_value,raw_reference,created_at,provider,provider_retrieved_at)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING transaction_id""",uuid4(),event.chain,event.transaction_hash.lower(),event.block_number,event.observed_at,"OBSERVED",event.from_address,event.to_address,float(event.amount) if event.contract_address is None else None,json.dumps(event.raw_provider_reference),now,event.provider,now)
                    await conn.execute("INSERT INTO transaction_transfers(transaction_id,transfer_type,asset,amount,source_address,destination_address,contract_address,token_id,raw_reference,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING",tx_id,"token" if event.contract_address else "native",event.asset,event.amount,event.from_address,event.to_address,event.contract_address or "",event.token_id or "",json.dumps(event.raw_provider_reference),now)
                    await conn.execute("INSERT INTO case_transactions(case_id,transaction_id,relation_type,created_at) VALUES($1,$2,'REALTIME',$3) ON CONFLICT DO NOTHING",UUID(watch.case_id),tx_id,now)
                    evidence_id=await conn.fetchval("SELECT evidence_id FROM evidence WHERE case_id=$1 AND chain=$2 AND tx_hash=$3 AND evidence_type='REALTIME_TRANSACTION'",UUID(watch.case_id),event.chain,event.transaction_hash)
                    if not evidence_id:
                        evidence_id=await conn.fetchval("""INSERT INTO evidence(evidence_id,case_id,evidence_type,chain,tx_hash,source,captured_at,metadata,created_at)
                        VALUES($1,$2,'REALTIME_TRANSACTION',$3,$4,$5,$6,$7,$8) RETURNING evidence_id""",uuid4(),UUID(watch.case_id),event.chain,event.transaction_hash,event.provider,event.received_at,json.dumps({"event_id":event.event_id,"block_number":event.block_number,"confirmation_state":event.confirmation_state,"raw_provider_reference":event.raw_provider_reference}),now)
                    edge_id=None
                    if trace_id:
                        hop=await conn.fetchval("SELECT COALESCE(MAX(hop),-1)+1 FROM graph_edges WHERE case_id=$1 AND source_wallet=$2",UUID(watch.case_id),event.from_address)
                        edge_id=await conn.fetchval("INSERT INTO graph_edges(edge_id,case_id,transaction_id,source_wallet,destination_wallet,asset,amount,timestamp,hop,created_at,trace_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING RETURNING edge_id",uuid4(),UUID(watch.case_id),tx_id,event.from_address,event.to_address,event.asset,event.amount,event.observed_at,hop,now,trace_id)
                    await conn.execute("INSERT INTO realtime_event_applications(event_id,case_id,watch_id,transaction_id,evidence_id,applied_at) VALUES($1,$2,$3,$4,$5,$6)",event.event_id,UUID(watch.case_id),UUID(watch.watch_id),tx_id,evidence_id,now)
                    await conn.execute("UPDATE realtime_events SET processing_status='APPLIED' WHERE event_id=$1",event.event_id)
                    await conn.execute("UPDATE watch_targets SET last_event_at=$3,last_processed_block=$4,last_processed_event=$5 WHERE watch_id=$1 AND case_id=$2",UUID(watch.watch_id),UUID(watch.case_id),event.received_at,event.block_number,event.event_id)
                return RealtimeApplicationResult(event=event.model_copy(update={"processing_status":RealtimeProcessingStatus.APPLIED}),case_id=watch.case_id,watch_id=watch.watch_id,transaction_id=str(tx_id),evidence_id=str(evidence_id),graph_edge_id=str(edge_id) if edge_id else None,new_wallet=not bool(known_destination))
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime event application failed") from exc

    async def timeline(self,case_id:str):
        async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM investigation_timeline WHERE case_id=$1 ORDER BY timestamp DESC",UUID(case_id))
        return [TimelineEvent(event_id=str(row["event_id"]),case_id=str(row["case_id"]),timestamp=row["timestamp"],event_type=row["event_type"],summary=row["summary"],source=row["source"],evidence_ids=json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or []),metadata=json.loads(row["metadata"]) if isinstance(row["metadata"],str) else (row["metadata"] or {})) for row in rows]

    async def change_sets(self,case_id:str):
        async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM change_sets WHERE case_id=$1 ORDER BY created_at DESC",UUID(case_id))
        return [InvestigationChangeSet(change_set_id=str(row["change_set_id"]),case_id=str(row["case_id"]),event_id=row["realtime_event_id"] or "",created_at=row["created_at"],before=json.loads(row["before_state"]) if isinstance(row["before_state"],str) else (row["before_state"] or {}),after=json.loads(row["after_state"]) if isinstance(row["after_state"],str) else (row["after_state"] or {}),changes=json.loads(row["changes"]) if isinstance(row["changes"],str) else (row["changes"] or {})) for row in rows]

    async def alerts(self,case_id:str):
        async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM alerts WHERE case_id=$1 ORDER BY created_at DESC",UUID(case_id))
        return [Alert(alert_id=str(row["alert_id"]),case_id=str(row["case_id"]),subject_id=row["subject_id"],alert_type=row["alert_type"],title=row["title"],explanation=row["explanation"],severity=row["severity"],status=row["status"],risk_delta=float(row["risk_delta"]),pattern_ids=json.loads(row["pattern_ids"]) if isinstance(row["pattern_ids"],str) else (row["pattern_ids"] or []),evidence_ids=json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or []),created_at=row["created_at"]) for row in rows]

    async def all_alerts(self):
        async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM alerts ORDER BY created_at DESC")
        return [Alert(alert_id=str(row["alert_id"]),case_id=str(row["case_id"]),subject_id=row["subject_id"],alert_type=row["alert_type"],title=row["title"],explanation=row["explanation"],severity=row["severity"],status=row["status"],risk_delta=float(row["risk_delta"]),pattern_ids=json.loads(row["pattern_ids"]) if isinstance(row["pattern_ids"],str) else (row["pattern_ids"] or []),evidence_ids=json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or []),created_at=row["created_at"]) for row in rows]

    async def append_timeline(self,event:TimelineEvent):
        async with self._require_pool().acquire() as conn:
            await conn.execute("INSERT INTO investigation_timeline(event_id,case_id,timestamp,event_type,summary,source,evidence_ids,metadata) VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(event_id) DO NOTHING",UUID(event.event_id),UUID(event.case_id),event.timestamp,event.event_type,event.summary,event.source,json.dumps(event.evidence_ids),json.dumps(event.metadata))

    async def append_change_set(self,change_set:InvestigationChangeSet):
        async with self._require_pool().acquire() as conn:
            await conn.execute("INSERT INTO change_sets(change_set_id,case_id,realtime_event_id,created_at,before_state,after_state,changes) VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(change_set_id) DO NOTHING",UUID(change_set.change_set_id),UUID(change_set.case_id),change_set.event_id,change_set.created_at,json.dumps(change_set.before),json.dumps(change_set.after),json.dumps(change_set.changes))

    async def create_alert(self,alert:Alert,fingerprint:str):
        async with self._require_pool().acquire() as conn:
            inserted=await conn.fetchval("INSERT INTO alerts(alert_id,case_id,subject_id,alert_type,title,explanation,severity,status,risk_delta,pattern_ids,evidence_ids,fingerprint,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT(fingerprint) DO NOTHING RETURNING alert_id",UUID(alert.alert_id),UUID(alert.case_id),alert.subject_id,alert.alert_type,alert.title,alert.explanation,alert.severity,alert.status,alert.risk_delta,json.dumps(alert.pattern_ids),json.dumps(alert.evidence_ids),fingerprint,alert.created_at)
            return alert if inserted else None

    def _alert_from_row(self,row):
        return Alert(alert_id=str(row["alert_id"]),case_id=str(row["case_id"]),subject_id=row["subject_id"],alert_type=row["alert_type"],title=row["title"],explanation=row["explanation"],severity=row["severity"],status=row["status"],risk_delta=float(row["risk_delta"]),pattern_ids=json.loads(row["pattern_ids"]) if isinstance(row["pattern_ids"],str) else (row["pattern_ids"] or []),evidence_ids=json.loads(row["evidence_ids"]) if isinstance(row["evidence_ids"],str) else (row["evidence_ids"] or []),created_at=row["created_at"])

    async def get_alert(self,case_id: str,alert_id: str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: row=await conn.fetchrow("SELECT * FROM alerts WHERE case_id=$1 AND alert_id=$2",UUID(case_id),UUID(alert_id))
            return self._alert_from_row(row) if row else None
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Alert could not be retrieved") from exc

    async def review_alert(self,case_id: str,alert_id: str,review: AlertReviewRequest):
        from .persistence import DatabaseError
        target={AlertReviewAction.ACKNOWLEDGE:AlertStatus.ACKNOWLEDGED,AlertReviewAction.DISMISS:AlertStatus.DISMISSED,AlertReviewAction.ESCALATE:AlertStatus.ESCALATED}[review.action]
        now=datetime.now(timezone.utc)
        allowed={AlertStatus.NEW:{AlertStatus.ACKNOWLEDGED,AlertStatus.DISMISSED,AlertStatus.ESCALATED},AlertStatus.ACKNOWLEDGED:{AlertStatus.DISMISSED,AlertStatus.ESCALATED},AlertStatus.ESCALATED:{AlertStatus.ACKNOWLEDGED,AlertStatus.DISMISSED},AlertStatus.DISMISSED:set()}
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    row=await conn.fetchrow("SELECT * FROM alerts WHERE case_id=$1 AND alert_id=$2 FOR UPDATE",UUID(case_id),UUID(alert_id))
                    if not row: raise ValueError("Alert not found")
                    current=AlertStatus(row["status"])
                    if current==target: return self._alert_from_row(row)
                    if target not in allowed[current]: raise ValueError(f"Cannot transition alert from {current} to {target}")
                    await conn.execute("UPDATE alerts SET status=$3,updated_at=$4,reviewed_at=$4,reviewed_by=$5 WHERE case_id=$1 AND alert_id=$2",UUID(case_id),UUID(alert_id),target,now,review.actor_id)
                    await conn.execute("INSERT INTO alert_reviews(review_id,alert_id,case_id,from_status,to_status,action,note,actor_id,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",uuid4(),UUID(alert_id),UUID(case_id),current,target,review.action,review.note,review.actor_id,now)
                    row=await conn.fetchrow("SELECT * FROM alerts WHERE case_id=$1 AND alert_id=$2",UUID(case_id),UUID(alert_id))
                    return self._alert_from_row(row)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Alert review could not be persisted") from exc

    async def alert_reviews(self,case_id: str,alert_id: str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM alert_reviews WHERE case_id=$1 AND alert_id=$2 ORDER BY created_at DESC",UUID(case_id),UUID(alert_id))
            return [AlertReview(review_id=str(row["review_id"]),alert_id=str(row["alert_id"]),case_id=str(row["case_id"]),from_status=row["from_status"],to_status=row["to_status"],action=row["action"],note=row["note"],actor_id=row["actor_id"],created_at=row["created_at"]) for row in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Alert review history could not be retrieved") from exc

    async def get_realtime_event(self,event_id:str):
        async with self._require_pool().acquire() as conn:
            row=await conn.fetchrow("SELECT * FROM realtime_events WHERE event_id=$1",event_id)
        return self._event_from_row(row) if row else None

    async def list_realtime_events(self,case_id:str,limit:int=50):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT DISTINCT ON (e.event_id) e.* FROM realtime_events e JOIN realtime_event_applications a ON a.event_id=e.event_id WHERE a.case_id=$1 ORDER BY e.event_id,e.received_at DESC LIMIT $2",UUID(case_id),max(1,min(limit,500)))
            return [self._event_from_row(row) for row in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime events could not be retrieved") from exc

    async def record_realtime_attempt(self,event_id: str,status: RealtimeProcessingStatus,error: str|None = None)->RealtimeProcessingAttempt:
        from .persistence import DatabaseError
        now=datetime.now(timezone.utc)
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    number=await conn.fetchval("UPDATE realtime_events SET attempt_count=attempt_count+1,processing_status=$2,error=$3,next_attempt_at=NULL,dead_lettered_at=NULL WHERE event_id=$1 RETURNING attempt_count",event_id,status,error)
                    if number is None: raise ValueError("Realtime event not found")
                    attempt=RealtimeProcessingAttempt(attempt_id=str(uuid4()),event_id=event_id,attempt_number=int(number),status=status,error=error,started_at=now,completed_at=now)
                    await conn.execute("INSERT INTO processing_attempts(attempt_id,event_id,attempt_number,status,error,started_at,completed_at) VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(event_id,attempt_number) DO UPDATE SET status=EXCLUDED.status,error=EXCLUDED.error,completed_at=EXCLUDED.completed_at",UUID(attempt.attempt_id),event_id,attempt.attempt_number,status,error,now,now)
                    return attempt
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime processing attempt could not be recorded") from exc

    async def realtime_attempts(self,event_id: str)->list[RealtimeProcessingAttempt]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM processing_attempts WHERE event_id=$1 ORDER BY attempt_number",event_id)
            return [RealtimeProcessingAttempt(attempt_id=str(row["attempt_id"]),event_id=row["event_id"],attempt_number=row["attempt_number"],status=row["status"],error=row["error"],started_at=row["started_at"],completed_at=row["completed_at"]) for row in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime processing attempts could not be retrieved") from exc

    async def mark_realtime_failure(self,event_id: str,error: str,max_attempts: int,retry_delay_seconds: int)->RealtimeEvent:
        from .persistence import DatabaseError
        now=datetime.now(timezone.utc)
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("""UPDATE realtime_events SET processing_status=CASE WHEN attempt_count >= $2 THEN 'DEAD_LETTER' ELSE 'RETRY_PENDING' END,error=$3,next_attempt_at=CASE WHEN attempt_count >= $2 THEN NULL ELSE $4::timestamptz END,dead_lettered_at=CASE WHEN attempt_count >= $2 THEN $5::timestamptz ELSE NULL END WHERE event_id=$1""",event_id,max(1,max_attempts),error,now+timedelta(seconds=max(1,retry_delay_seconds)),now)
                row=await conn.fetchrow("SELECT * FROM realtime_events WHERE event_id=$1",event_id)
            if not row: raise ValueError("Realtime event not found")
            return self._event_from_row(row)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime event failure state could not be persisted") from exc

    async def list_realtime_failures(self,limit: int = 100)->list[RealtimeOperationalEvent]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT * FROM realtime_events WHERE processing_status IN ('RETRY_PENDING','FAILED','DEAD_LETTER') ORDER BY received_at LIMIT $1",max(1,min(limit,500)))
            result=[]
            for row in rows:
                event=self._event_from_row(row); result.append(RealtimeOperationalEvent(event=event,attempts=await self.realtime_attempts(event.event_id),retryable=event.processing_status in {RealtimeProcessingStatus.RETRY_PENDING,RealtimeProcessingStatus.FAILED}))
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime failure queue could not be retrieved") from exc

    async def reset_realtime_event(self,event_id: str)->RealtimeEvent:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("UPDATE realtime_events SET processing_status='RECEIVED',attempt_count=0,error=NULL,next_attempt_at=NULL,dead_lettered_at=NULL WHERE event_id=$1",event_id)
                row=await conn.fetchrow("SELECT * FROM realtime_events WHERE event_id=$1",event_id)
            if not row: raise ValueError("Realtime event not found")
            return self._event_from_row(row)
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Realtime event could not be reset") from exc
