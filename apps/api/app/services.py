from collections import deque
from datetime import datetime, timezone
from uuid import uuid4
import logging
import time
from decimal import Decimal
from .config import settings
from .domain import *
from .provider import BlockchainProvider
from .graph_engine import GraphAnalyzer, GraphBuilder, amount_for_filter

logger=logging.getLogger("crypto_fraud_intelligence")

class CaseRepository:
    async def create(self,data:CaseCreate)->InvestigationCase: raise NotImplementedError
    async def list_cases(self)->list[CaseListItem]: raise NotImplementedError
    async def dashboard_summary(self)->DashboardSummary: raise NotImplementedError
    async def list_evidence(self,case_id:str)->list[Evidence]: raise NotImplementedError
    async def update_case(self,case_id:str,data:CasePatch)->InvestigationCase|None: raise NotImplementedError
    async def close_case(self,case_id:str)->InvestigationCase|None: raise NotImplementedError
    async def reopen_case(self,case_id:str)->InvestigationCase|None: raise NotImplementedError
    async def set_workflow_stage(self,case_id:str,stage:CaseWorkflowStage,provider:str|None=None,result_count:int|None=None,error:str|None=None,evidence_ids:list[str]|None=None)->InvestigationCase|None: raise NotImplementedError
    async def workflow_events(self,case_id:str)->list[dict]: raise NotImplementedError
    async def get(self,case_id:str)->InvestigationCase|None: raise NotImplementedError
    async def add_wallet(self,case_id:str,wallet:WalletCreate)->InvestigationCase: raise NotImplementedError
    async def add_transaction(self,case_id:str,transaction:TransactionCreate)->InvestigationCase: raise NotImplementedError
    async def persist_trace(self,result:TraceResult)->None: raise NotImplementedError
    async def list_traces(self,case_id:str)->list[TraceResult]: raise NotImplementedError
    async def get_trace(self,case_id:str,trace_id:str)->TraceResult|None: raise NotImplementedError
    async def persist_patterns(self, observations:list[PatternObservation])->list[PatternObservation]: raise NotImplementedError
    async def list_patterns(self, case_id:str, trace_id:str|None=None)->list[PatternObservation]: raise NotImplementedError
    async def list_patterns_by_trace(self, trace_id:str)->list[PatternObservation]: raise NotImplementedError
    async def get_pattern(self, case_id:str, pattern_id:str)->PatternObservation|None: raise NotImplementedError
    async def pattern_summary(self, case_id:str, trace_id:str|None=None)->PatternSummary: raise NotImplementedError
    async def latest_risk(self, case_id:str, subject_id:str|None=None)->RiskAssessment|None: raise NotImplementedError
    async def risk_history(self, case_id:str, subject_id:str|None=None)->list[RiskAssessment]: raise NotImplementedError
    async def risk_by_trace(self, trace_id:str)->list[RiskAssessment]: raise NotImplementedError
    async def risk_by_subject(self, subject_id:str)->list[RiskAssessment]: raise NotImplementedError
    async def risk_by_wallet(self, wallet_id:str)->list[RiskAssessment]: raise NotImplementedError
    async def persist_risk(self, assessment:RiskAssessment, alerts:list[RiskAlertCandidate])->RiskAssessment: raise NotImplementedError
    async def risk_factors(self, case_id:str, assessment_id:str|None=None)->list[RiskFactor]: raise NotImplementedError
    async def risk_alerts(self, case_id:str, subject_id:str|None=None)->list[RiskAlertCandidate]: raise NotImplementedError
    async def append_audit_event(self, event:AuditEvent)->None: raise NotImplementedError
    async def audit_events(self, case_id: str) -> list[AuditEvent]: raise NotImplementedError
    async def create_watch(self, watch:WatchTarget)->WatchTarget: raise NotImplementedError
    async def list_watches(self, case_id:str)->list[WatchTarget]: raise NotImplementedError
    async def list_all_watches(self, chain:Chain|None=None)->list[WatchTarget]: raise NotImplementedError
    async def get_watch(self, case_id:str, watch_id:str)->WatchTarget|None: raise NotImplementedError
    async def update_watch(self, watch:WatchTarget)->WatchTarget: raise NotImplementedError
    async def ingest_realtime_event(self, event:RealtimeEvent)->tuple[RealtimeEvent,bool]: raise NotImplementedError
    async def apply_realtime_event(self, event:RealtimeEvent, watch:WatchTarget)->RealtimeApplicationResult: raise NotImplementedError
    async def timeline(self, case_id:str)->list[TimelineEvent]: raise NotImplementedError
    async def change_sets(self, case_id:str)->list[InvestigationChangeSet]: raise NotImplementedError
    async def alerts(self, case_id:str)->list[Alert]: raise NotImplementedError
    async def all_alerts(self)->list[Alert]: raise NotImplementedError
    async def append_timeline(self, event:TimelineEvent)->None: raise NotImplementedError
    async def append_change_set(self, change_set:InvestigationChangeSet)->None: raise NotImplementedError
    async def create_alert(self, alert:Alert, fingerprint:str)->Alert|None: raise NotImplementedError
    async def get_alert(self, case_id: str, alert_id: str) -> Alert | None: raise NotImplementedError
    async def review_alert(self, case_id: str, alert_id: str, review: AlertReviewRequest) -> Alert: raise NotImplementedError
    async def alert_reviews(self, case_id: str, alert_id: str) -> list[AlertReview]: raise NotImplementedError
    async def get_realtime_event(self, event_id:str)->RealtimeEvent|None: raise NotImplementedError
    async def record_realtime_attempt(self,event_id: str,status: RealtimeProcessingStatus,error: str|None = None)->RealtimeProcessingAttempt: raise NotImplementedError
    async def realtime_attempts(self,event_id: str)->list[RealtimeProcessingAttempt]: raise NotImplementedError
    async def mark_realtime_failure(self,event_id: str,error: str,max_attempts: int,retry_delay_seconds: int)->RealtimeEvent: raise NotImplementedError
    async def list_realtime_failures(self,limit: int = 100)->list[RealtimeOperationalEvent]: raise NotImplementedError
    async def persist_cross_chain_observation(self,case_id:str,observation:CrossChainObservationCreate): raise NotImplementedError
    async def cross_chain_transfers(self,case_id:str)->list[Transfer]: raise NotImplementedError
    async def persist_bridge_definition(self,definition:BridgeDefinition): raise NotImplementedError
    async def persist_bridge_interaction(self,case_id:str,item:BridgeInteraction): raise NotImplementedError
    async def persist_cross_chain_link(self,case_id:str,link:CrossChainLink): raise NotImplementedError
    async def persist_cross_chain_trace(self,trace:CrossChainTrace): raise NotImplementedError
    async def cross_chain_links(self,case_id:str)->list[CrossChainLink]: raise NotImplementedError
    async def persist_cross_chain_patterns(self,patterns:list[CrossChainPatternObservation]): raise NotImplementedError
    async def cross_chain_patterns(self,case_id:str)->list[CrossChainPatternObservation]: raise NotImplementedError
    async def entity_attributions(self, entity_id: str) -> list[AddressAttribution]: raise NotImplementedError
    async def attribution_sources(self) -> list[AttributionSource]: raise NotImplementedError
    async def sanctions_records(self) -> list[SanctionsRecord]: raise NotImplementedError
    async def persist_screening(self, case_id: str | None, result: AddressScreeningResult) -> AddressScreeningResult: raise NotImplementedError
    async def case_screenings(self, case_id: str) -> list[AddressScreeningResult]: raise NotImplementedError
    async def persist_evidence_manifest(self, manifest: EvidenceManifest, evidence: list[Evidence], events: list[EvidenceChainEvent]) -> EvidenceManifest: raise NotImplementedError
    async def evidence_ledger(self, case_id: str) -> list[EvidenceLedgerEntry]: raise NotImplementedError
    async def evidence_manifests(self, case_id: str) -> list[EvidenceManifest]: raise NotImplementedError
    async def evidence_chain(self, case_id: str, evidence_id: str) -> list[EvidenceChainEvent]: raise NotImplementedError
    async def persist_report(self, report: InvestigationReport) -> InvestigationReport: raise NotImplementedError
    async def list_reports(self, case_id: str) -> list[InvestigationReport]: raise NotImplementedError
    async def get_report(self, case_id: str, report_id: str) -> InvestigationReport | None: raise NotImplementedError
    async def related_cases(self, case_id: str) -> list[CaseLink]: raise NotImplementedError
    async def intelligence_sources(self) -> list[IntelligenceSource]: raise NotImplementedError
    async def threat_indicators(self, chain: Chain | None = None) -> list[ThreatIndicator]: raise NotImplementedError
    async def contract_security_findings(self, chain: Chain, address: str) -> list[ContractSecurityFinding]: raise NotImplementedError

class TraceService:
    def __init__(self,provider:BlockchainProvider, provider_registry=None):
        self.provider=provider; self.provider_registry=provider_registry; self.builder=GraphBuilder(); self.analyzer=GraphAnalyzer()
    async def trace(self,case_id:str,request:TraceRequest)->TraceResult:
        provider=self.provider_registry.get(request.chain) if self.provider_registry else self.provider
        started=time.monotonic(); retrieved_at=datetime.now(timezone.utc); root=normalize_address(request.chain,request.address); queue=deque([(root,0)]); seen={root}; depths={root:0}; transfers=[]; evidence=[]; observed_tx=set(); partial=False; discovered=0; skipped=0; duplicates=0
        while queue:
            if time.monotonic()-started >= request.max_duration: partial=True; break
            address,depth=queue.popleft()
            if depth>=request.max_hops: continue
            rows=await provider.get_address_transfers(address,request.chain,page_size=settings.alchemy_page_size,max_pages=settings.alchemy_max_pages,max_transactions=min(settings.alchemy_max_transactions,request.max_transactions))
            for transfer in rows:
                discovered += 1
                actual_source=normalize_address(transfer.chain,transfer.source); actual_target=normalize_address(transfer.chain,transfer.destination)
                if request.direction==TraceDirection.FORWARD and actual_source!=address: skipped += 1; continue
                if request.direction==TraceDirection.BACKWARD and actual_target!=address: skipped += 1; continue
                if request.start_time and transfer.timestamp and transfer.timestamp<request.start_time: skipped += 1; continue
                if request.end_time and transfer.timestamp and transfer.timestamp>request.end_time: skipped += 1; continue
                if request.asset_filter and request.asset_filter.lower() not in {transfer.asset.lower(),(transfer.contract_address or '').lower()}: skipped += 1; continue
                if request.min_transfer_value and amount_for_filter(transfer)<Decimal(str(request.min_transfer_value)): skipped += 1; continue
                if transfer.tx_hash in observed_tx: duplicates += 1; continue
                if transfer.tx_hash not in observed_tx and len(observed_tx)>=request.max_transactions: partial=True; break
                observed_tx.add(transfer.tx_hash); transfers.append(transfer)
                ev=Evidence(evidence_id=str(uuid4()),case_id=case_id,type="TRANSACTION",chain=transfer.chain,tx_hash=transfer.tx_hash,source=transfer.provider,captured_at=datetime.now(timezone.utc),metadata={"block_number":transfer.block_number,"asset":transfer.asset,"amount":transfer.amount,"from_address":transfer.source,"to_address":transfer.destination,"raw_reference":transfer.raw_reference})
                evidence.append(ev)
                neighbor=actual_target if request.direction==TraceDirection.FORWARD else actual_source
                if neighbor and neighbor not in seen:
                    if len(seen)>=request.max_nodes: partial=True; break
                    seen.add(neighbor); depths[neighbor]=depth+1; queue.append((neighbor,depth+1))
                if len(transfers)>=request.max_edges: partial=True; break
            if partial: break
        graph,nodes,edges=self.builder.build(transfers,root,depths)
        evidence_by_tx={e.tx_hash:e.evidence_id for e in evidence}
        for edge in edges: edge.evidence_id=evidence_by_tx.get(edge.transaction_hash)
        analysis_graph=graph.reverse(copy=True) if request.direction==TraceDirection.BACKWARD else graph
        paths=self.analyzer.paths(analysis_graph,root); flows=self.analyzer.flows(edges); metrics=self.analyzer.metrics(graph,nodes,edges,root,paths)
        limits=TraceLimits(max_hops=request.max_hops,max_nodes=request.max_nodes,max_edges=request.max_edges,max_transactions=request.max_transactions,max_duration=request.max_duration)
        status="PARTIAL" if partial else "COMPLETED"
        duration_ms = int((time.monotonic() - started) * 1000)
        mode = DataMode.DEVELOPMENT_FIXTURE if provider.name == "Development Fixture" else DataMode.HISTORICAL
        pages_req = max(1, (discovered + settings.alchemy_page_size - 1) // settings.alchemy_page_size)
        pages_rec = max(1, (len(transfers) + settings.alchemy_page_size - 1) // settings.alchemy_page_size)
        acq = AcquisitionStatistics(
            discovered=discovered,
            normalized=len(transfers),
            persisted=len(transfers),
            duplicates=duplicates,
            failed=0,
            skipped=skipped,
            provider=provider.name,
            mode=mode,
            retrieved_at=retrieved_at,
            network=request.chain.value,
            wallet=root,
            pages_requested=pages_req,
            pages_received=pages_rec,
            transactions_discovered=discovered,
            transactions_normalized=len(transfers),
            transactions_persisted=len(transfers),
            transfers_discovered=discovered,
            transfers_persisted=len(transfers),
            duration_ms=duration_ms
        )
        return TraceResult(case_id=case_id,trace_id=str(uuid4()),root_address=root,mode=mode,provider=provider.name,nodes=nodes,edges=edges,signals=[],evidence=evidence,status=status,direction=request.direction,limits=limits,metrics=metrics,paths=paths,flows=flows,acquisition=acq,limitations=["Trace is bounded by configured hop, node, edge, transaction, and duration limits.","Attribution, cross-chain correlation, and realtime observations are separate source-backed workflows."])
