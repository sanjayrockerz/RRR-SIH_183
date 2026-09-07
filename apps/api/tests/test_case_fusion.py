from datetime import datetime, timezone

import pytest

from app.case_fusion_service import CaseFusionService, compare_fingerprints
from app.domain import CaseFingerprint


def fingerprint(case_id, *, wallets=(), vasps=(), bridges=(), patterns=()):
    return CaseFingerprint(case_id=case_id, wallet_ids=list(wallets), vasp_ids=list(vasps), bridge_ids=list(bridges), pattern_types=list(patterns), first_activity=datetime(2026, 1, 1, tzinfo=timezone.utc), last_activity=datetime(2026, 1, 2, tzinfo=timezone.utc))


def test_shared_wallet_is_confirmed_and_explainable():
    relation = compare_fingerprints(fingerprint("a", wallets=["w1"]), fingerprint("b", wallets=["w1"]))
    assert relation.relationship == "CONFIRMED_STRUCTURAL_OVERLAP"
    assert "shared persisted wallet infrastructure" in relation.reasons
    assert "criminal" not in " ".join(relation.reasons).lower()


@pytest.mark.parametrize("field,reason", [("vasps", "same source-backed VASP/entity attribution"), ("bridges", "same persisted bridge service")])
def test_shared_vasp_or_bridge_is_confirmed(field, reason):
    relation = compare_fingerprints(fingerprint("a", **{field: ["x"]}), fingerprint("b", **{field: ["x"]}))
    assert relation.relationship == "CONFIRMED_STRUCTURAL_OVERLAP"
    assert reason in relation.reasons


def test_unrelated_cases_are_not_linked_and_score_is_deterministic():
    left = fingerprint("a", patterns=["RAPID_HOP"])
    right = fingerprint("b", patterns=["FAN_IN"])
    assert compare_fingerprints(left, right) is None
    similar = fingerprint("c", vasps=["v1"], patterns=["RAPID_HOP"])
    first = compare_fingerprints(left, similar)
    second = compare_fingerprints(left, similar)
    assert first.model_dump() == second.model_dump()


@pytest.mark.asyncio
async def test_clusters_only_use_confirmed_persisted_overlap():
    class Repository:
        async def case_fusion_fingerprints(self):
            return [fingerprint("a", wallets=["w"]), fingerprint("b", wallets=["w"]), fingerprint("c")]

    result = await CaseFusionService(Repository()).clusters()
    assert len(result.clusters) == 1
    assert result.clusters[0].case_ids == ["a", "b"]
