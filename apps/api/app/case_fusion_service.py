"""Deterministic, explainable case-fusion calculations over persisted fingerprints."""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256

from .domain import (
    CaseFingerprint,
    CaseFusionCluster,
    CaseFusionClustersResponse,
    CaseFusionRelation,
    CaseFusionResponse,
)


def _by_id(items: list[dict]) -> dict[str, dict]:
    return {str(item.get("id")): item for item in items if item.get("id") is not None}


def compare_fingerprints(left: CaseFingerprint, right: CaseFingerprint) -> CaseFusionRelation | None:
    wallets = sorted(set(left.wallet_ids) & set(right.wallet_ids))
    transactions = sorted(set(left.transaction_ids) & set(right.transaction_ids))
    vasps = sorted(set(left.vasp_ids) & set(right.vasp_ids))
    bridges = sorted(set(left.bridge_ids) & set(right.bridge_ids))
    patterns = sorted(set(left.pattern_types) & set(right.pattern_types))

    structural = bool(wallets or transactions or vasps or bridges)
    temporal = False
    if left.first_activity and right.first_activity and left.last_activity and right.last_activity:
        temporal = max(left.first_activity, right.first_activity) <= min(left.last_activity, right.last_activity) or abs((left.first_activity - right.first_activity).total_seconds()) <= timedelta(days=7).total_seconds()

    # Each component is bounded and deliberately inspectable; no probabilistic model is implied.
    similarity = min(1.0, (0.35 if vasps else 0) + (0.25 if bridges else 0) + (0.25 if patterns else 0) + (0.15 if temporal else 0))
    structural_score = min(1.0, (0.40 if wallets else 0) + (0.25 if transactions else 0) + (0.20 if vasps else 0) + (0.20 if bridges else 0))
    if not structural and similarity < 0.25:
        return None

    reasons: list[str] = []
    if wallets:
        reasons.append("shared persisted wallet infrastructure")
    if transactions:
        reasons.append("shared persisted transaction")
    if vasps:
        reasons.append("same source-backed VASP/entity attribution")
    if bridges:
        reasons.append("same persisted bridge service")
    if patterns:
        reasons.append("common observed laundering pattern(s): " + ", ".join(patterns))
    if temporal:
        reasons.append("similar temporal activity window")

    return CaseFusionRelation(
        related_case_id=right.case_id,
        relationship="CONFIRMED_STRUCTURAL_OVERLAP" if structural else "POSSIBLE_INFRASTRUCTURE_SIMILARITY",
        score=round(structural_score if structural else similarity, 4),
        shared_wallets=[_by_id(left.wallets).get(item, {"id": item}) for item in wallets],
        shared_transactions=[{"id": item} for item in transactions],
        shared_vasps=[_by_id(left.vasps).get(item, {"id": item}) for item in vasps],
        shared_bridges=[_by_id(left.bridges).get(item, {"id": item}) for item in bridges],
        shared_patterns=patterns,
        reasons=reasons,
    )


class CaseFusionService:
    def __init__(self, repository):
        self.repository = repository

    async def for_case(self, case_id: str) -> CaseFusionResponse:
        fingerprints = await self.repository.case_fusion_fingerprints()
        selected = next((item for item in fingerprints if item.case_id == case_id), None)
        if selected is None:
            raise KeyError(case_id)
        relations = [relation for item in fingerprints if item.case_id != case_id if (relation := compare_fingerprints(selected, item)) is not None]
        relations.sort(key=lambda item: (-item.score, item.related_case_id))
        return CaseFusionResponse(case_id=case_id, fingerprint=selected, related_cases=relations, limitations=["Correlations describe persisted infrastructure overlap or similarity; they do not establish common ownership or criminal attribution."])

    async def clusters(self) -> CaseFusionClustersResponse:
        fingerprints = await self.repository.case_fusion_fingerprints()
        parent = {item.case_id: item.case_id for item in fingerprints}

        def find(item: str) -> str:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        relations: list[tuple[CaseFusionRelation, str, str]] = []
        for index, left in enumerate(fingerprints):
            for right in fingerprints[index + 1:]:
                relation = compare_fingerprints(left, right)
                if relation and relation.relationship == "CONFIRMED_STRUCTURAL_OVERLAP":
                    parent[find(left.case_id)] = find(right.case_id)
                    relations.append((relation, left.case_id, right.case_id))

        groups: dict[str, set[str]] = {}
        for case_id in parent:
            groups.setdefault(find(case_id), set()).add(case_id)
        clusters = []
        for members in groups.values():
            if len(members) < 2:
                continue
            member_ids = sorted(members)
            matching = [item for item in relations if item[1] in members and item[2] in members]
            reasons = sorted({reason for relation, _, _ in matching for reason in relation.reasons})
            infrastructure = sorted({label for relation, _, _ in matching for label in (["wallet"] if relation.shared_wallets else []) + (["transaction"] if relation.shared_transactions else []) + (["VASP/entity"] if relation.shared_vasps else []) + (["bridge"] if relation.shared_bridges else [])})
            digest = sha256("|".join(member_ids).encode()).hexdigest()[:16]
            clusters.append(CaseFusionCluster(cluster_id=f"fusion-{digest}", case_ids=member_ids, score=round(max(item[0].score for item in matching), 4), shared_infrastructure=infrastructure, reasons=reasons))
        clusters.sort(key=lambda item: item.cluster_id)
        return CaseFusionClustersResponse(status="READY", clusters=clusters, limitations=["Clusters are derived from persisted case observations and do not establish common ownership or criminal attribution."])
