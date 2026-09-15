from datetime import datetime, timezone
from uuid import uuid4

from ..domain import Chain
from ..threat_intel.schemas import ThreatIntelStatus
from .rules import RecommendationContext, RecommendationRuleset, build_recommendations
from .schemas import RecommendationResponse


class RecommendationService:
    def __init__(self, repository, threat_intel_service, vasp_resolver):
        self.repository = repository
        self.threat_intel_service = threat_intel_service
        self.vasp_resolver = vasp_resolver

    async def latest(self, case_id: str) -> RecommendationResponse:
        return await self.repository.latest_recommendations(case_id)

    async def refresh(self, case_id: str) -> RecommendationResponse:
        case = await self.repository.get(case_id)
        if not case:
            raise ValueError("Case not found")
        assessment = await self.repository.latest_risk(case_id)
        watches = await self.repository.list_watches(case_id)
        related = await self.repository.related_cases(case_id)
        threat = await self.repository.threat_intel_observations(case_id=case_id)
        vasp = await self.vasp_resolver(case.latest_trace) if case.latest_trace else []
        cross_links = await self.repository.cross_chain_links(case_id)
        unresolved = any(not link.destination or str(link.correlation_level).upper() in {"UNRESOLVED", "UNKNOWN"} for link in cross_links)
        context = RecommendationContext(case_id=case_id, risk_band=assessment.band.value if assessment else None, risk_delta=assessment.delta.delta if assessment and assessment.delta else 0, current_score=assessment.score if assessment else None, vasp_candidates=[item.model_dump(mode="json") for item in vasp], active_watch=any(str(item.status) == "ACTIVE" for item in watches), related_case_count=len(related), direct_threat_matches=[item.model_dump(mode="json") for item in threat if item.match_type == ThreatIntelStatus.DIRECT_MATCH], unresolved_cross_chain=unresolved)
        snapshot_id = str(uuid4())
        generated_at = datetime.now(timezone.utc)
        recommendations = build_recommendations(context, RecommendationRuleset(), generated_at=generated_at, snapshot_id=snapshot_id)
        await self.repository.persist_recommendations(recommendations)
        return RecommendationResponse(status="READY", case_id=case_id, snapshot_id=snapshot_id, ruleset_version=RecommendationRuleset().version, recommendations=recommendations, generated_at=generated_at)
