import json
from datetime import datetime, timezone
from uuid import UUID

from .recommendations.schemas import Recommendation, RecommendationResponse


class RecommendationPersistenceMixin:
    async def persist_recommendations(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        if not recommendations:
            return []
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    for item in recommendations:
                        await conn.execute(
                            """INSERT INTO recommendation_snapshots
                            (recommendation_id,snapshot_id,case_id,ruleset_version,priority,code,title,reason,evidence_refs,action_target,generated_at)
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                            UUID(item.recommendation_id), UUID(item.snapshot_id), UUID(item.case_id),
                            item.ruleset_version, item.priority.value, item.code, item.title, item.reason,
                            json.dumps(item.evidence_refs), item.action_target, item.generated_at,
                        )
            return recommendations
        except Exception as exc:
            import asyncpg
            if isinstance(exc, (asyncpg.PostgresError, ValueError)):
                from .persistence import DatabaseError
                raise DatabaseError("Recommendation snapshot could not be persisted") from exc
            raise

    async def latest_recommendations(self, case_id: str) -> RecommendationResponse:
        try:
            async with self._require_pool().acquire() as conn:
                snapshot = await conn.fetchval("SELECT snapshot_id FROM recommendation_snapshots WHERE case_id=$1 ORDER BY generated_at DESC LIMIT 1", UUID(case_id))
                if not snapshot:
                    return RecommendationResponse(status="NO_DATA", case_id=case_id, ruleset_version="phase7-recommendations-v1", recommendations=[], generated_at=datetime.now(timezone.utc))
                rows = await conn.fetch("SELECT * FROM recommendation_snapshots WHERE case_id=$1 AND snapshot_id=$2 ORDER BY CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 ELSE 2 END, code", UUID(case_id), snapshot)
            return RecommendationResponse(
                status="READY", case_id=case_id, snapshot_id=str(snapshot), ruleset_version=rows[0]["ruleset_version"],
                recommendations=[Recommendation(recommendation_id=str(row["recommendation_id"]), case_id=case_id, snapshot_id=str(row["snapshot_id"]), priority=row["priority"], code=row["code"], title=row["title"], reason=row["reason"], evidence_refs=json.loads(row["evidence_refs"]) if isinstance(row["evidence_refs"], str) else list(row["evidence_refs"] or []), action_target=row["action_target"], generated_at=row["generated_at"], ruleset_version=row["ruleset_version"]) for row in rows],
                generated_at=rows[0]["generated_at"],
            )
        except Exception as exc:
            import asyncpg
            if isinstance(exc, (asyncpg.PostgresError, ValueError)):
                from .persistence import DatabaseError
                raise DatabaseError("Recommendations could not be retrieved") from exc
            raise
