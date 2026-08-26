"""Application orchestration for provider events and incremental retracing."""
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4
import json

from .domain import *
from .realtime import AlchemyWebhookNormalizer, RealtimeProvider


class RealtimeService:
    def __init__(self, repository, provider: RealtimeProvider, pattern_service, risk_service, cross_chain_service=None):
        self.repository = repository
        self.provider = provider
        self.pattern_service = pattern_service
        self.risk_service = risk_service
        self.normalizer = AlchemyWebhookNormalizer()
        self.cross_chain_service = cross_chain_service

    async def create_watch(self, case_id: str, request: WatchCreate) -> WatchTarget:
        if not await self.repository.get(case_id):
            raise ValueError("Case not found")
        WalletCreate(address=request.address, chain=request.chain)
        requested = await self.provider.subscribe_to_address_activity(request.address, request.chain, str(uuid4()))
        watch = requested.model_copy(update={
            "case_id": case_id,
            "address": request.address.lower(),
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
        event = event.model_copy(update={"provider": "SIMULATED EVENT SOURCE", "processing_status": RealtimeProcessingStatus.NORMALIZED})
        return await self._process_events([event])

    async def _process_events(self, events: list[RealtimeEvent]):
        results = []
        for event in events:
            stored, duplicate = await self.repository.ingest_realtime_event(event)
            if duplicate:
                results.append(RealtimeApplicationResult(event=stored, case_id="", watch_id="", duplicate=True))
                continue
            watches = [w for w in await self._all_watches(event.chain) if w.status == WatchTargetStatus.ACTIVE and (w.address.lower() == event.from_address.lower() or w.address.lower() == event.to_address.lower())]
            for watch in watches:
                before = await self.repository.get(watch.case_id)
                application = await self.repository.apply_realtime_event(stored, watch)
                await self._derive_investigation_state(before, application)
                results.append(application)
        return results

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
        if case.latest_trace:
            try:
                attributions = await self._case_attributions(case.latest_trace)
                patterns = await self.pattern_service.analyze(case.latest_trace, PatternAnalyzeRequest(trace_id=case.latest_trace.trace_id), attributions)
                if patterns:
                    await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case.case_id,timestamp=now,event_type="PATTERN_ANALYZED",summary=f"{len(patterns)} evidence-backed behavioral observation(s) evaluated after new activity.",source="PatternEngine",evidence_ids=list(dict.fromkeys(e for p in patterns for e in p.evidence_ids)),metadata={"pattern_ids":[p.pattern_id for p in patterns]}))
                assessment = await self.risk_service.assess(case.case_id, RiskAssessRequest(trace_id=case.latest_trace.trace_id))
                await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case.case_id,timestamp=now,event_type="RISK_REASSESSED",summary=f"Investigative risk posture recalculated from persisted evidence: {assessment.band} ({assessment.score:.1f}/100).",source="RuleBasedRiskEngine",evidence_ids=assessment.evidence_ids,metadata={"assessment_id":assessment.assessment_id,"delta":assessment.delta.delta if assessment.delta else 0}))
                if assessment.delta and assessment.delta.delta > 0:
                    fingerprint = sha256(json.dumps({"case":case.case_id,"assessment":assessment.assessment_id,"delta":assessment.delta.delta,"factors":sorted(f.definition_id for f in assessment.factors)},sort_keys=True).encode()).hexdigest()
                    await self.repository.create_alert(Alert(alert_id=str(uuid4()),case_id=case.case_id,subject_id=assessment.subject.address,alert_type="RISK_REASSESSMENT",title="NEW INVESTIGATIVE ALERT",explanation="New observed blockchain activity changed the persisted investigative risk posture. Review the linked evidence and factors; this is not a criminality determination.",severity=assessment.band,risk_delta=assessment.delta.delta,pattern_ids=assessment.pattern_ids,evidence_ids=assessment.evidence_ids,created_at=now), fingerprint)
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
