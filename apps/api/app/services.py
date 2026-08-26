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
    async def append_timeline(self, event:TimelineEvent)->None: raise NotImplementedError
    async def append_change_set(self, change_set:InvestigationChangeSet)->None: raise NotImplementedError
    async def create_alert(self, alert:Alert, fingerprint:str)->Alert|None: raise NotImplementedError
    async def get_realtime_event(self, event_id:str)->RealtimeEvent|None: raise NotImplementedError

class TraceService:
    def __init__(self,provider:BlockchainProvider):
        self.provider=provider; self.builder=GraphBuilder(); self.analyzer=GraphAnalyzer()
    async def trace(self,case_id:str,request:TraceRequest)->TraceResult:
        started=time.monotonic(); root=request.address.lower(); queue=deque([(root,0)]); seen={root}; depths={root:0}; transfers=[]; evidence=[]; observed_tx=set(); partial=False
        while queue:
            if time.monotonic()-started >= request.max_duration: partial=True; break
            address,depth=queue.popleft()
            if depth>=request.max_hops: continue
            rows=await self.provider.get_address_transfers(address,request.chain,page_size=settings.alchemy_page_size,max_pages=settings.alchemy_max_pages,max_transactions=min(settings.alchemy_max_transactions,request.max_transactions))
            for transfer in rows:
                actual_source=transfer.source.lower(); actual_target=transfer.destination.lower()
                if request.direction==TraceDirection.FORWARD and actual_source!=address: continue
                if request.direction==TraceDirection.BACKWARD and actual_target!=address: continue
                if request.start_time and transfer.timestamp and transfer.timestamp<request.start_time: continue
                if request.end_time and transfer.timestamp and transfer.timestamp>request.end_time: continue
                if request.asset_filter and request.asset_filter.lower() not in {transfer.asset.lower(),(transfer.contract_address or '').lower()}: continue
                if request.min_transfer_value and amount_for_filter(transfer)<Decimal(str(request.min_transfer_value)): continue
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
        return TraceResult(case_id=case_id,trace_id=str(uuid4()),root_address=root,mode=DataMode.HISTORICAL,provider=self.provider.name,nodes=nodes,edges=edges,signals=[],evidence=evidence,status=status,direction=request.direction,limits=limits,metrics=metrics,paths=paths,flows=flows,limitations=["Entity attribution is not implemented.","Cross-chain and real-time ingestion are not implemented."])
