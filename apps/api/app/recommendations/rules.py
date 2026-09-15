from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid5

from ..config import settings
from .schemas import Recommendation, RecommendationPriority


@dataclass(frozen=True)
class RecommendationRuleset:
    version: str = settings.recommendation_ruleset_version
    vasp_max_hops: int = settings.recommendation_vasp_max_hops
    risk_delta_threshold: float = settings.recommendation_risk_delta_threshold


@dataclass
class RecommendationContext:
    case_id: str
    risk_band: str | None = None
    risk_delta: float = 0
    current_score: float | None = None
    vasp_candidates: list[dict] = field(default_factory=list)
    active_watch: bool = False
    related_case_count: int = 0
    direct_threat_matches: list[dict] = field(default_factory=list)
    unresolved_cross_chain: bool = False


_CONFIDENCE_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CONFIRMED": 4}
_PRIORITY_RANK = {RecommendationPriority.P1: 0, RecommendationPriority.P2: 1, RecommendationPriority.P3: 2}


def build_recommendations(context: RecommendationContext, ruleset: RecommendationRuleset | None = None, *, generated_at: datetime, snapshot_id: str) -> list[Recommendation]:
    rules = ruleset or RecommendationRuleset()
    candidates: list[Recommendation] = []
    nearest = next((item for item in context.vasp_candidates if item.get("classification") != "UNRESOLVED"), None)
    if nearest and _CONFIDENCE_RANK.get(str(nearest.get("attribution_confidence", "UNKNOWN")), 0) >= _CONFIDENCE_RANK["HIGH"] and int(nearest.get("hop_distance", 999)) <= rules.vasp_max_hops:
        confidence = nearest.get("attribution_confidence", "HIGH")
        amount = nearest.get("observed_linked_amount", "observed value")
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P1, "REVIEW_VASP_CANDIDATE", "Review probable VASP candidate", f"High-confidence source-backed custodial endpoint is {nearest.get('hop_distance')} hops from the reported wallet with {amount} of observed linked value ({confidence} confidence).", nearest.get("evidence_ids", []), "/vasp-intelligence"))
    if context.risk_delta > rules.risk_delta_threshold and str(context.risk_band) in {"HIGH", "CRITICAL"}:
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P1, "ESCALATE_RISK_CHANGE", "Escalate material risk change", f"Risk increased by {context.risk_delta:g} points and is currently {context.risk_band}.", [], "/risk"))
    if context.active_watch and context.risk_delta > 0:
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P1, "ESCALATE_ACTIVE_WATCH", "Escalate active watch activity", f"Risk increased by {context.risk_delta:g} points after activity on an active case watch.", [], "/monitoring"))
    if context.related_case_count > 0:
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P2, "REVIEW_RELATED_CASES", "Review related investigations", f"Case Fusion identified shared persisted infrastructure across {context.related_case_count} related investigation(s).", [], "/case-fusion"))
    if context.direct_threat_matches:
        refs = [str(item.get("observation_id")) for item in context.direct_threat_matches if item.get("observation_id")]
        source = context.direct_threat_matches[0].get("source", "an external source")
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P2, "REVIEW_THREAT_INTEL_MATCH", "Review external threat-intelligence match", f"A source-backed external indicator from {source} matched a wallet in this case.", refs, "/threat-intelligence"))
    if context.unresolved_cross_chain:
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P2, "REVIEW_CROSS_CHAIN_GAP", "Review unresolved cross-chain gap", "Cross-chain activity was observed or inferred but no verified destination relationship was established.", [], "/cross-chain"))
    if not nearest and context.active_watch:
        candidates.append(_recommendation(context.case_id, snapshot_id, rules.version, generated_at, RecommendationPriority.P3, "CONTINUE_MONITORING", "Continue monitoring", "No actionable VASP candidate is currently source-backed and the wallet watch remains active.", [], "/monitoring"))
    candidates.sort(key=lambda item: (_PRIORITY_RANK[item.priority], item.code))
    return candidates


def _recommendation(case_id, snapshot_id, version, generated_at, priority, code, title, reason, refs, target):
    return Recommendation(recommendation_id=str(uuid5(UUID(snapshot_id), code)), case_id=case_id, snapshot_id=snapshot_id, priority=priority, code=code, title=title, reason=reason, evidence_refs=sorted(set(refs or [])), action_target=target, generated_at=generated_at, ruleset_version=version)
