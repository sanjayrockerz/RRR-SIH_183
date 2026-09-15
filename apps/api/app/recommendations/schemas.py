from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel


class RecommendationPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Recommendation(BaseModel):
    recommendation_id: str
    case_id: str
    priority: RecommendationPriority
    code: str
    title: str
    reason: str
    evidence_refs: list[str] = []
    action_target: str | None = None
    generated_at: datetime
    ruleset_version: str
    snapshot_id: str | None = None


class RecommendationResponse(BaseModel):
    status: str
    case_id: str
    snapshot_id: str | None = None
    ruleset_version: str
    recommendations: list[Recommendation] = []
    generated_at: datetime
    limitation: str = "Recommendations are deterministic review prompts, not legal conclusions or automatic enforcement actions."
