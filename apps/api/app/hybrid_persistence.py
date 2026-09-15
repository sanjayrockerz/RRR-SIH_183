import json
from uuid import UUID, uuid4

import asyncpg


class HybridPersistenceMixin:
    async def persist_hybrid_snapshot(self, intelligence):
        try:
            async with self._require_pool().acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO hybrid_intelligence_snapshots
                    (id,case_id,ruleset_version,priority,recommendation_text,reason_codes_json,
                     signal_summary_json,evidence_refs_json,limitations_json,previous_priority,
                     priority_changed,state_hash,generated_at,created_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                    ON CONFLICT(case_id,state_hash) DO NOTHING RETURNING *""",
                    uuid4(), UUID(intelligence.case_id), intelligence.ruleset_version,
                    intelligence.priority.value, intelligence.recommendation, json.dumps(intelligence.reason_codes),
                    json.dumps(intelligence.model_dump(mode="json")), json.dumps(intelligence.evidence_refs),
                    json.dumps(intelligence.limitations), intelligence.previous_priority.value if intelligence.previous_priority else None,
                    intelligence.priority_changed, intelligence.state_hash, intelligence.generated_at, intelligence.generated_at,
                )
            return intelligence if row else await self.get_latest_hybrid_snapshot(intelligence.case_id)
        except (asyncpg.PostgresError, ValueError) as exc:
            from .persistence import DatabaseError
            raise DatabaseError("Hybrid intelligence snapshot could not be persisted") from exc

    async def get_latest_hybrid_snapshot(self, case_id: str):
        rows = await self._hybrid_rows("case_id=$1", UUID(case_id), limit=1)
        return rows[0] if rows else None

    async def list_hybrid_snapshots(self, case_id: str, limit: int = 50):
        return await self._hybrid_rows("case_id=$1", UUID(case_id), limit=max(1, min(limit, 500)))

    async def _hybrid_rows(self, predicate: str, *args, limit: int):
        try:
            async with self._require_pool().acquire() as conn:
                rows = await conn.fetch(f"SELECT * FROM hybrid_intelligence_snapshots WHERE {predicate} ORDER BY generated_at DESC LIMIT ${len(args)+1}", *args, limit)
            result = []
            for row in rows:
                item = dict(row); item["id"] = str(item["id"]); item["case_id"] = str(item["case_id"])
                for key, default in (("reason_codes_json", []), ("signal_summary_json", {}), ("evidence_refs_json", []), ("limitations_json", [])):
                    value = item.get(key, default)
                    item[key] = json.loads(value) if isinstance(value, str) else (value or default)
                result.append(item)
            return result
        except (asyncpg.PostgresError, ValueError) as exc:
            from .persistence import DatabaseError
            raise DatabaseError("Hybrid intelligence snapshots could not be retrieved") from exc
