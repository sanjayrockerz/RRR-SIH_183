"""Application orchestration for provider events and incremental retracing."""
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4
import json

from .domain import *
from .realtime import AlchemyWebhookNormalizer, RealtimeProvider
from .config import settings
import logging


class RealtimeService:
    def __init__(self, repository, provider: RealtimeProvider, pattern_service, risk_service, cross_chain_service=None, graph_projection=None, event_bus=None):
        self.repository = repository
        self.provider = provider
        self.pattern_service = pattern_service
        self.risk_service = risk_service
        self.normalizer = AlchemyWebhookNormalizer()
        self.cross_chain_service = cross_chain_service
        self.graph_projection = graph_projection
        self.event_bus = event_bus

    async def _publish(self,event_type: str,event: RealtimeEvent,case_id: str | None = None,payload: dict | None = None):
        if not self.event_bus: return
        mode="DEVELOPMENT_SYNTHETIC" if event.provider=="DEVELOPMENT SYNTHETIC" else "LIVE"
        await self.event_bus.publish(event_type,case_id=case_id,wallet_id=event.from_address,transaction_hash=event.transaction_hash,chain=event.chain,source=event.provider,mode=mode,payload=payload)

    async def create_watch(self, case_id: str, request: WatchCreate) -> WatchTarget:
        if not await self.repository.get(case_id):
            raise ValueError("Case not found")
        WalletCreate(address=request.address, chain=request.chain)
        watch_id = str(uuid4())
        if request.source in {"SIMULATED", "DEVELOPMENT_SYNTHETIC"}:
            provider_name = "DEVELOPMENT SYNTHETIC" if request.source == "DEVELOPMENT_SYNTHETIC" else "SIMULATED EVENT SOURCE"
            requested = WatchTarget(watch_id=watch_id, case_id=case_id, address=request.address, chain=request.chain, source=request.source, created_at=datetime.now(timezone.utc), status=WatchTargetStatus.ACTIVE, provider=provider_name)
        else:
            requested = await self.provider.subscribe_to_address_activity(request.address, request.chain, watch_id)
            if not requested:
                raise ValueError("Realtime provider is not configured. Configure Alchemy or explicitly use DEVELOPMENT_SYNTHETIC mode.")
        watch = requested.model_copy(update={
            "case_id": case_id,
            "address": normalize_address(request.chain,request.address),
            "chain": request.chain,
            "source": request.source,
            "expansion_policy": request.expansion_policy,
            "max_hops": request.max_hops,
            "max_new_nodes_per_event": request.max_new_nodes_per_event,
            "max_new_edges_per_event": request.max_new_edges_per_event,
            "max_value": request.max_value,
            "allowed_assets": request.allowed_assets,
        })
        return await self.repository.create_watch(watch)

    async def watches(self, case_id: str):
        return await self.repository.list_watches(case_id)

    async def set_status(self, case_id: str, watch_id: str, status: WatchTargetStatus):
        watch = await self.repository.get_watch(case_id, watch_id)
        if not watch:
            raise ValueError("Watch target not found")
        if status in {WatchTargetStatus.PAUSED, WatchTargetStatus.STOPPED} and watch.subscription_id:
            await self.provider.unsubscribe(watch.subscription_id)
        return await self.repository.update_watch(watch.model_copy(update={"status": status}))

    async def receive_webhook(self, payload: dict, raw_body: bytes, signature: str | None):
        verifier = getattr(self.provider, "verify_signature", None)
        if not verifier or not verifier(raw_body, signature):
            raise PermissionError("Webhook signature validation failed")
        events = self.normalizer.normalize(payload)
        return await self._process_events(events)

    async def receive_simulated(self, event: RealtimeEvent):
        """Explicit test seam; responses remain marked SIMULATED by the API."""
        WalletCreate(address=event.from_address, chain=event.chain)
        WalletCreate(address=event.to_address, chain=event.chain)
        TransactionCreate(tx_hash=event.transaction_hash, chain=event.chain)
        # Preserve the explicit development engine provenance. Generic test
        # events remain marked as simulated, while the deterministic synthetic
        # source stays distinguishable in evidence and UI telemetry.
        provider = event.provider if event.provider == "DEVELOPMENT SYNTHETIC" else "SIMULATED EVENT SOURCE"
        event = event.model_copy(update={"provider": provider, "processing_status": RealtimeProcessingStatus.NORMALIZED})
        return await self._process_events([event])

    async def _process_events(self, events: list[RealtimeEvent]):
        results = []
        for event in events:
            await self._publish("REALTIME_EVENT_RECEIVED",event,payload={"processing_status":"RECEIVED"})
            stored, duplicate = await self.repository.ingest_realtime_event(event)
            if duplicate:
                results.append(RealtimeApplicationResult(event=stored, case_id="", watch_id="", duplicate=True))
                await self._publish("REALTIME_EVENT_RECEIVED",stored,payload={"processing_status":"DUPLICATE"})
                continue
            try:
                await self._publish("TRANSFER_NORMALIZED",stored,payload={"processing_status":"NORMALIZED"})
                watches = [w for w in await self._all_watches(event.chain) if w.status == WatchTargetStatus.ACTIVE and (normalize_address(event.chain,w.address) == normalize_address(event.chain,event.from_address) or normalize_address(event.chain,w.address) == normalize_address(event.chain,event.to_address))]
                for watch in watches:
                    before = await self.repository.get(watch.case_id)
                    application = await self.repository.apply_realtime_event(stored, watch)
                    await self._publish("TRANSACTION_DETECTED",stored,watch.case_id,{"graph_edge_id":application.graph_edge_id,"evidence_id":application.evidence_id})
                    await self._publish("GRAPH_UPDATED",stored,watch.case_id,{"graph_edge_id":application.graph_edge_id})
                    if self.graph_projection:
                        projected_edges = await self.graph_projection.project_incremental(watch.case_id, stored, application.graph_edge_id, application.evidence_id)
                        if projected_edges:
                            await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=watch.case_id,timestamp=stored.observed_at or stored.received_at,event_type="GRAPH_PROJECTION_UPDATED",summary="Optional relationship projection updated from the observed realtime event.",source="Neo4jProjection",evidence_ids=[application.evidence_id] if application.evidence_id else [],metadata={"event_id":stored.event_id,"graph_edge_id":application.graph_edge_id}))
                    await self._derive_investigation_state(before, application)
                    results.append(application)
                await self.repository.record_realtime_attempt(stored.event_id, RealtimeProcessingStatus.APPLIED)
                await self._publish("EVIDENCE_CREATED",stored,payload={"processing_status":"APPLIED"})
            except Exception as exc:
                logging.getLogger("crypto_fraud_intelligence").exception("realtime_event_processing_failed", extra={"event_id": stored.event_id, "provider": stored.provider, "operation": "process_realtime_event"})
                try:
                    await self.repository.record_realtime_attempt(stored.event_id, RealtimeProcessingStatus.FAILED, type(exc).__name__)
                    await self.repository.mark_realtime_failure(stored.event_id, type(exc).__name__, settings.realtime_max_processing_attempts, settings.realtime_retry_delay_seconds)
                except Exception:
                    logging.getLogger("crypto_fraud_intelligence").exception("database_error", extra={"operation":"mark_realtime_failure"})
                raise
        return results

    async def replay(self, event_id: str):
        event = await self.repository.reset_realtime_event(event_id)
        return await self._process_events([event])

    async def _all_watches(self, chain):
        return await self.repository.list_all_watches(chain)

    async def _derive_investigation_state(self, before: InvestigationCase | None, application: RealtimeApplicationResult):
        if not before:
            return
        case = await self.repository.get(application.case_id)
        if not case:
            return
        now = application.event.observed_at or application.event.received_at
        evidence_ids = [application.evidence_id] if application.evidence_id else []
        await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()), case_id=case.case_id, timestamp=now, event_type="BLOCKCHAIN_ACTIVITY", summary=f"Observed {application.event.asset} movement {application.event.from_address} → {application.event.to_address} from {application.event.provider}.", source=application.event.provider, evidence_ids=evidence_ids, metadata={"transaction_hash": application.event.transaction_hash, "confirmation_state": application.event.confirmation_state}))
        if self.cross_chain_service:
            try:
                cross_trace=await self.cross_chain_service.analyze(case.case_id,CrossChainAnalyzeRequest(root_chain=application.event.chain,root_address=application.event.from_address,max_hops=4,max_cross_chain_hops=1,max_nodes=100,max_edges=200,max_transactions=100))
                if cross_trace.cross_chain_links:
                    await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case.case_id,timestamp=now,event_type="CROSS_CHAIN_ACTIVITY",summary="Cross-chain relationship analysis updated from the new observed event; relationships are explicit confidence-scored inferences.",source="CrossChainEngine",evidence_ids=list(dict.fromkeys(e for link in cross_trace.cross_chain_links for e in link.evidence_ids)),metadata={"trace_id":cross_trace.trace_id,"cross_chain_hops":cross_trace.cross_chain_hops}))
            except ValueError:
                pass
        if case.latest_trace and case.latest_trace.trace_id:
            try:
                attributions = await self._case_attributions(case.latest_trace)
                patterns = await self.pattern_service.analyze(case.latest_trace, PatternAnalyzeRequest(trace_id=case.latest_trace.trace_id), attributions)
                if patterns:
                    await self._publish("PATTERN_DETECTED",application.event,case.case_id,{"pattern_count":len(patterns),"pattern_ids":[p.pattern_id for p in patterns]})
                    await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case.case_id,timestamp=now,event_type="PATTERN_ANALYZED",summary=f"{len(patterns)} evidence-backed behavioral observation(s) evaluated after new activity.",source="PatternEngine",evidence_ids=list(dict.fromkeys(e for p in patterns for e in p.evidence_ids)),metadata={"pattern_ids":[p.pattern_id for p in patterns]}))
                assessment = await self.risk_service.assess(case.case_id, RiskAssessRequest(trace_id=case.latest_trace.trace_id))
                await self._publish("RISK_REASSESSED",application.event,case.case_id,{"assessment_id":assessment.assessment_id,"score":assessment.score,"band":assessment.band,"delta":assessment.delta.delta if assessment.delta else 0})
                await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case.case_id,timestamp=now,event_type="RISK_REASSESSED",summary=f"Investigative risk posture recalculated from persisted evidence: {assessment.band} ({assessment.score:.1f}/100).",source="RuleBasedRiskEngine",evidence_ids=assessment.evidence_ids,metadata={"assessment_id":assessment.assessment_id,"delta":assessment.delta.delta if assessment.delta else 0}))
                if assessment.delta and assessment.delta.delta > 0:
                    fingerprint = sha256(json.dumps({"case":case.case_id,"assessment":assessment.assessment_id,"delta":assessment.delta.delta,"factors":sorted(f.definition_id for f in assessment.factors)},sort_keys=True).encode()).hexdigest()
                    await self.repository.create_alert(Alert(alert_id=str(uuid4()),case_id=case.case_id,subject_id=assessment.subject.address,alert_type="RISK_REASSESSMENT",title="NEW INVESTIGATIVE ALERT",explanation="New observed blockchain activity changed the persisted investigative risk posture. Review the linked evidence and factors; this is not a criminality determination.",severity=assessment.band,risk_delta=assessment.delta.delta,pattern_ids=assessment.pattern_ids,evidence_ids=assessment.evidence_ids,created_at=now), fingerprint)
                    await self._publish("ALERT_CREATED",application.event,case.case_id,{"risk_delta":assessment.delta.delta,"score":assessment.score,"band":assessment.band})
            except ValueError:
                # A realtime event remains persisted even when there is no trace to
                # reassess. The timeline above is the durable observation record.
                pass
        before_count = len(before.transactions)
        after_count = len(case.transactions)
        await self.repository.append_change_set(InvestigationChangeSet(change_set_id=str(uuid4()),case_id=case.case_id,event_id=application.event.event_id,created_at=now,before={"transaction_count":before_count},after={"transaction_count":after_count},changes={"transactions_added":after_count-before_count,"graph_edge_id":application.graph_edge_id,"evidence_id":application.evidence_id}))

    async def _case_attributions(self, trace):
        from .attribution import AttributionEngine, NearestEntityResolver
        entities, sources, records = await self.repository.attribution_catalog()
        return NearestEntityResolver(AttributionEngine(entities, sources, records)).resolve(trace)

    def capabilities(self):
        return self.provider.capabilities()

    async def health(self):
        return await self.provider.health()
