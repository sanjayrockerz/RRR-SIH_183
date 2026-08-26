"""Deterministic, evidence-backed investigative risk posture calculation."""
from datetime import datetime, timezone
from uuid import uuid4

from .domain import *

_CONFIDENCE_RANK={ConfidenceLevel.UNKNOWN:0,ConfidenceLevel.LOW:1,ConfidenceLevel.MEDIUM:2,ConfidenceLevel.HIGH:3,ConfidenceLevel.CONFIRMED:4}


def default_risk_config() -> RiskScoringConfig:
    definitions=[
        RiskFactorDefinition(id="pattern:rapid_hop",name="Rapid-hop behavior",category="TRANSACTION_BEHAVIOR",default_weight=20,max_contribution=30,explanation_template="Observed rapid-hop behavior in {count} persisted pattern observation(s)."),
        RiskFactorDefinition(id="pattern:fan_out",name="Fan-out behavior",category="TRANSACTION_BEHAVIOR",default_weight=12,max_contribution=20,explanation_template="Observed fan-out behavior across {count} persisted pattern observation(s)."),
        RiskFactorDefinition(id="pattern:fan_in",name="Fan-in behavior",category="TRANSACTION_BEHAVIOR",default_weight=12,max_contribution=20,explanation_template="Observed fan-in behavior across {count} persisted pattern observation(s)."),
        RiskFactorDefinition(id="pattern:peel_chain",name="Peel-chain-like flow",category="FLOW_CHARACTERISTICS",default_weight=15,max_contribution=20,explanation_template="Observed repeated forwarding with residual value in {count} pattern observation(s)."),
        RiskFactorDefinition(id="pattern:consolidation",name="Consolidation behavior",category="FLOW_CHARACTERISTICS",default_weight=12,max_contribution=20,explanation_template="Observed multiple sources consolidating at a common destination."),
        RiskFactorDefinition(id="pattern:burst_activity",name="Burst activity",category="TEMPORAL_CHARACTERISTICS",default_weight=10,max_contribution=15,explanation_template="Observed high transaction density in {count} pattern observation(s)."),
        RiskFactorDefinition(id="pattern:dormant_activation",name="Dormant-to-active transition",category="TEMPORAL_CHARACTERISTICS",default_weight=8,max_contribution=12,explanation_template="Observed an inactivity interval followed by activity."),
        RiskFactorDefinition(id="entity:mixer",name="Mixer interaction",category="ENTITY_EXPOSURE",default_weight=25,max_contribution=35,explanation_template="Observed interaction with an address attributed to a mixer."),
        RiskFactorDefinition(id="entity:bridge",name="Bridge interaction",category="ENTITY_EXPOSURE",default_weight=8,max_contribution=12,explanation_template="Observed interaction with an address attributed to a bridge."),
        RiskFactorDefinition(id="entity:vasp",name="Entity exposure",category="ENTITY_EXPOSURE",default_weight=10,max_contribution=20,explanation_template="Observed a path reaching a source-backed attributed entity."),
        RiskFactorDefinition(id="pattern:cross_chain_hop",name="Cross-chain hop",category="CROSS_CHAIN_BEHAVIOR",default_weight=12,max_contribution=20,explanation_template="Observed {count} evidence-backed cross-chain movement observation(s)."),
        RiskFactorDefinition(id="pattern:bridge_hop",name="Bridge-mediated movement",category="CROSS_CHAIN_BEHAVIOR",default_weight=10,max_contribution=18,explanation_template="Observed bridge-mediated movement in {count} persisted observation(s)."),
        RiskFactorDefinition(id="graph:hop_depth",name="Graph hop depth",category="GRAPH_CHARACTERISTICS",default_weight=5,max_contribution=10,explanation_template="The bounded graph reached {hops} observed hops."),
    ]
    return RiskScoringConfig(version="phase6-default-v1",factors=definitions,thresholds=RiskBandThresholds())


class RiskEngine:
    """Pure calculation boundary. It performs no persistence and no external I/O."""
    def assess(self, trace: TraceResult, patterns: list[PatternObservation], attributions: list[NearestEntityResult], subject: RiskSubject, config: RiskScoringConfig | None = None, previous: RiskAssessment | None = None, calculated_at: datetime | None = None) -> RiskAssessment:
        config=config or default_risk_config()
        if not config.factors: config=default_risk_config().model_copy(update={"version":config.version,"thresholds":config.thresholds})
        self._validate_config(config)
        now=calculated_at or datetime.now(timezone.utc)
        factors=[]
        for definition in config.factors:
            if not definition.enabled: continue
            if definition.id.startswith("pattern:"):
                pattern_type=definition.id.split(":",1)[1].upper()
                matches=[p for p in self._unique_patterns(patterns) if p.pattern_type==pattern_type and p.evidence_ids]
                if not matches: continue
                factors.append(self._pattern_factor(definition,matches))
            elif definition.id.startswith("entity:"):
                entity_type=definition.id.split(":",1)[1].upper()
                matches=[a for a in self._unique_attributions(attributions) if a.entity.entity_type==entity_type and self._entity_evidence(a)]
                if not matches: continue
                factors.append(self._entity_factor(definition,matches))
            elif definition.id=="graph:hop_depth" and trace.metrics.maximum_hop>=3:
                evidence=list(dict.fromkeys(e.evidence_id for e in trace.edges if e.evidence_id))
                if evidence: factors.append(RiskFactor(factor_id=str(uuid4()),definition_id=definition.id,name=definition.name,category=definition.category,contribution=min(definition.max_contribution,definition.default_weight),max_contribution=definition.max_contribution,explanation=definition.explanation_template.format(hops=trace.metrics.maximum_hop),confidence_level=ConfidenceLevel.MEDIUM,transaction_hashes=list(dict.fromkeys(e.transaction_hash for e in trace.edges)),evidence_ids=evidence,metadata={"maximum_hop":trace.metrics.maximum_hop}))
        score=round(min(100,max(0,sum(f.contribution for f in factors))),2)
        band=self._band(score,config.thresholds)
        priority,reason=self._priority(band,trace,now)
        delta=self._delta(previous,score,factors) if previous else RiskDelta(current_score=score,delta=score,new_factors=[f.definition_id for f in factors])
        evidence_ids=list(dict.fromkeys(evidence for factor in factors for evidence in factor.evidence_ids))
        pattern_ids=list(dict.fromkeys(pattern for factor in factors for pattern in factor.pattern_ids))
        entity_ids=list(dict.fromkeys(entity for factor in factors for entity in factor.entity_ids))
        return RiskAssessment(assessment_id=str(uuid4()),case_id=trace.case_id,trace_id=trace.trace_id,subject=subject,version=(previous.version+1 if previous else 1),score=score,band=band,priority=priority,priority_reason=reason,factors=factors,delta=delta,calculation_version=config.version,calculated_at=now,evidence_ids=evidence_ids,pattern_ids=pattern_ids,entity_ids=entity_ids,explanation="Investigative risk posture derived from source-backed observations and persisted blockchain evidence; it is not a legal or criminality determination.",previous_assessment_id=previous.assessment_id if previous else None)

    def _pattern_factor(self, definition, matches):
        evidence=list(dict.fromkeys(e for item in matches for e in item.evidence_ids)); txs=list(dict.fromkeys(t for item in matches for t in item.transaction_hashes)); patterns=[p.pattern_id for p in matches]; nodes=list(dict.fromkeys(n for item in matches for n in item.affected_nodes)); confidence=max((p.confidence_level for p in matches),key=lambda x:_CONFIDENCE_RANK[x],default=ConfidenceLevel.UNKNOWN); contribution=min(definition.max_contribution,definition.default_weight*len(matches))
        return RiskFactor(factor_id=str(uuid4()),definition_id=definition.id,name=definition.name,category=definition.category,contribution=contribution,max_contribution=definition.max_contribution,explanation=definition.explanation_template.format(count=len(matches)),confidence_level=confidence,pattern_ids=patterns,transaction_hashes=txs,evidence_ids=evidence,metadata={"affected_nodes":nodes,"observation_count":len(matches)})

    def _entity_factor(self, definition, matches):
        evidence=list(dict.fromkeys(e for item in matches for e in self._entity_evidence(item))); entities=list(dict.fromkeys(item.entity.entity_id for item in matches)); txs=list(dict.fromkeys(edge.transfer.tx_hash for item in matches for edge in item.path.edges)); contribution=min(definition.max_contribution,definition.default_weight*len(matches)); confidence=max((item.confidence for item in matches),key=lambda x:_CONFIDENCE_RANK[x],default=ConfidenceLevel.UNKNOWN)
        return RiskFactor(factor_id=str(uuid4()),definition_id=definition.id,name=definition.name,category=definition.category,contribution=contribution,max_contribution=definition.max_contribution,explanation=definition.explanation_template.format(count=len(matches)),confidence_level=confidence,entity_ids=entities,transaction_hashes=txs,evidence_ids=evidence,metadata={"entity_names":[item.entity.name for item in matches]})

    @staticmethod
    def _entity_evidence(item): return list(dict.fromkeys([e.evidence_id for e in item.evidence if e.evidence_id]+[edge.evidence_id for edge in item.path.edges if edge.evidence_id]))
    @staticmethod
    def _unique_patterns(patterns):
        unique={}
        for item in patterns:
            key=item.fingerprint or f"{item.pattern_type}:{','.join(sorted(item.transaction_hashes))}:{','.join(sorted(item.evidence_ids))}"
            unique[key]=item
        return list(unique.values())
    @staticmethod
    def _unique_attributions(attributions):
        unique={}
        for item in attributions: unique[f"{item.entity.entity_id}:{item.address.lower()}"]=item
        return list(unique.values())
    @staticmethod
    def _validate_config(config):
        t=config.thresholds
        if not t.guarded_min<=t.elevated_min<=t.high_min<=t.critical_min: raise ValueError("Risk band thresholds must be monotonic")
        if any(f.max_contribution<f.default_weight for f in config.factors if f.enabled): raise ValueError("Risk factor max contribution must be at least its default weight")
    @staticmethod
    def _band(score,thresholds):
        if score>=thresholds.critical_min:return RiskBand.CRITICAL
        if score>=thresholds.high_min:return RiskBand.HIGH
        if score>=thresholds.elevated_min:return RiskBand.ELEVATED
        if score>=thresholds.guarded_min:return RiskBand.GUARDED
        return RiskBand.LOW
    @staticmethod
    def _priority(band,trace,now):
        latest=max((e.transfer.timestamp for e in trace.edges if e.transfer.timestamp),default=None)
        recent=latest is not None and 0 <= (now-latest).total_seconds() <= 3600
        if recent and band in {RiskBand.HIGH,RiskBand.CRITICAL}: return InvestigativePriority.URGENT,"Recent observed activity falls within the one-hour freshness window."
        mapping={RiskBand.CRITICAL:InvestigativePriority.URGENT,RiskBand.HIGH:InvestigativePriority.PRIORITY,RiskBand.ELEVATED:InvestigativePriority.REVIEW,RiskBand.GUARDED:InvestigativePriority.REVIEW,RiskBand.LOW:InvestigativePriority.INFORMATIONAL}
        return mapping[band],"Priority reflects the calculated investigative risk posture; live monitoring is not inferred."
    def _delta(self,previous,score,factors):
        before={f.definition_id:f for f in previous.factors}; after={f.definition_id:f for f in factors}; new=[k for k in after if k not in before]; removed=[k for k in before if k not in after]; changed=[k for k in after if k in before and after[k].contribution!=before[k].contribution]
        return RiskDelta(previous_score=previous.score,current_score=score,delta=round(score-previous.score,2),new_factors=new,removed_factors=removed,changed_factors=changed)
