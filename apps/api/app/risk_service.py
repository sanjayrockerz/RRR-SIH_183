import logging
from datetime import datetime, timezone
from uuid import uuid4

from .attribution import AttributionEngine, NearestEntityResolver
from .domain import *
from .risk_engine import RiskEngine
from .synthetic_attribution import is_synthetic_trace, merge as merge_synthetic_attribution

logger=logging.getLogger("crypto_fraud_intelligence")

class RiskService:
    """Application boundary for deterministic risk reassessment."""
    def __init__(self, repository, engine: RiskEngine | None = None):
        self.repository=repository; self.engine=engine or RiskEngine()

    async def assess(self, case_id: str, request: RiskAssessRequest) -> RiskAssessment:
        case=await self.repository.get(case_id)
        if not case: raise ValueError("Case not found")
        trace=await self.repository.get_trace(case_id,request.trace_id) if request.trace_id else case.latest_trace
        if not trace: raise ValueError("No persisted trace for case")
        patterns=await self.repository.list_patterns(case_id,trace.trace_id)
        try:
            cross_patterns=await self.repository.cross_chain_patterns(case_id)
            patterns.extend(PatternObservation(pattern_id=item.pattern_id,case_id=item.case_id,trace_id=trace.trace_id,pattern_type=item.pattern_type,status=item.status,confidence_level=item.confidence_level,severity=item.severity,description=item.description,explanation=item.explanation,observed_at=item.observed_at,affected_edges=item.link_ids,evidence_ids=item.evidence_ids,metadata=item.metadata,fingerprint=item.fingerprint) for item in cross_patterns)
        except AttributeError:
            pass
        entities,sources,records=await self.repository.attribution_catalog()
        if is_synthetic_trace(trace):
            entities,sources,records=merge_synthetic_attribution(entities, sources, records)
        attributions=NearestEntityResolver(AttributionEngine(entities,sources,records)).resolve(trace)
        address=(request.subject_address or trace.root_address).lower()
        subject=RiskSubject(subject_id=address,case_id=case_id,chain=trace.nodes[0].chain if trace.nodes else Chain.ETHEREUM,address=address)
        previous=await self.repository.latest_risk(case_id,address)
        assessment=self.engine.assess(trace,patterns,[item for item in attributions if item.address.lower()==address or item.address.lower() in {n.address.lower() for n in trace.nodes}],subject,request.config,previous,datetime.now(timezone.utc),case_fraud_type=getattr(case,"fraud_type",""))
        alerts=[]
        if assessment.delta and assessment.delta.delta>0 and (assessment.delta.new_factors or assessment.delta.changed_factors or (previous and previous.band!=assessment.band)):
            alerts=[RiskAlertCandidate(candidate_id=str(uuid4()),case_id=case_id,subject_id=address,assessment_id=assessment.assessment_id,trigger="NEW INVESTIGATIVE SIGNAL: risk posture changed from persisted evidence",severity=assessment.band,risk_delta=assessment.delta.delta,pattern_ids=assessment.pattern_ids,evidence_ids=assessment.evidence_ids,created_at=assessment.calculated_at)]
        result=await self.repository.persist_risk(assessment,alerts)
        await self.repository.append_audit_event(AuditEvent(event_id=str(uuid4()),case_id=case_id,action="RISK_ASSESSED",resource_type="RISK_ASSESSMENT",resource_id=result.assessment_id,occurred_at=result.calculated_at,metadata={"score":result.score,"band":result.band,"version":result.version}))
        logger.info("risk_assessed",extra={"case_id":case_id,"assessment_id":result.assessment_id,"score":result.score,"band":result.band})
        return result

    async def latest(self,case_id:str,subject_id:str|None=None): return await self.repository.latest_risk(case_id,subject_id)
    async def history(self,case_id:str,subject_id:str|None=None): return await self.repository.risk_history(case_id,subject_id)
    async def trace(self,trace_id:str): return await self.repository.risk_by_trace(trace_id)
    async def subject(self,subject_id:str): return await self.repository.risk_by_subject(subject_id)
    async def wallet(self,wallet_id:str): return await self.repository.risk_by_wallet(wallet_id)
    async def factors(self,case_id:str,assessment_id:str|None=None): return await self.repository.risk_factors(case_id,assessment_id)
    async def alerts(self,case_id:str,subject_id:str|None=None): return await self.repository.risk_alerts(case_id,subject_id)

    async def delta(self,case_id:str,subject_id:str|None=None):
        history=await self.repository.risk_history(case_id,subject_id)
        if not history: return None
        return history[0].delta
