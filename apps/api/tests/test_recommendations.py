from datetime import datetime, timezone
from uuid import uuid4

from app.recommendations.rules import RecommendationContext, RecommendationRuleset, build_recommendations


def test_recommendation_rules_are_deterministic_and_prioritized():
    context = RecommendationContext(
        case_id="case-1", risk_band="CRITICAL", risk_delta=14, active_watch=True,
        related_case_count=2,
        vasp_candidates=[{"classification": "PROBABLE", "attribution_confidence": "HIGH", "hop_distance": 4, "observed_linked_amount": "100 USDT", "evidence_ids": ["ev-1"]}],
        direct_threat_matches=[{"observation_id": "obs-1", "source": "Chainabuse"}], unresolved_cross_chain=True,
    )
    first = build_recommendations(context, RecommendationRuleset(), generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), snapshot_id=str(uuid4()))
    second = build_recommendations(context, RecommendationRuleset(), generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), snapshot_id=str(uuid4()))
    assert [item.code for item in first] == ["ESCALATE_ACTIVE_WATCH", "ESCALATE_RISK_CHANGE", "REVIEW_VASP_CANDIDATE", "REVIEW_CROSS_CHAIN_GAP", "REVIEW_RELATED_CASES", "REVIEW_THREAT_INTEL_MATCH"]
    assert len({item.code for item in first}) == len(first)
    assert [(item.priority, item.code) for item in first] == [(item.priority, item.code) for item in second]


def test_continue_monitoring_is_low_priority_when_vasp_unresolved():
    items = build_recommendations(RecommendationContext(case_id="case-1", active_watch=True), generated_at=datetime.now(timezone.utc), snapshot_id=str(uuid4()))
    assert [(item.priority.value, item.code) for item in items] == [("P3", "CONTINUE_MONITORING")]
