import json
from uuid import UUID, uuid4

import asyncpg


class MLPersistenceMixin:
    async def create_assessment(self, record):
        """Insert one historical assessment. There is deliberately no update method."""
        assessment_id = UUID(record.get("id") or record["inference_id"] or str(uuid4()))
        provenance = record.get("provenance", {}) or {}
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute(
                    """INSERT INTO ml_wallet_assessments
                    (id,case_id,wallet_id,chain,address,normalized_address,model_name,model_version,
                     feature_schema_version,probability,classification,threshold,feature_hash,
                     features_json,top_features_json,observation_time,generated_at,status,limitations_json,
                     model_sha256,metadata_sha256,created_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)""",
                    assessment_id, UUID(record["case_id"]), UUID(record["wallet_id"]) if record.get("wallet_id") else None,
                    record["chain"], record["address"], record["address"].lower() if record["chain"] == "ethereum" else record["address"],
                    record.get("model_name"), record.get("model_version"), record.get("feature_schema_version"),
                    record.get("probability"), record.get("classification"), record.get("threshold"), record.get("feature_hash"),
                    json.dumps(record.get("features", {})), json.dumps(record.get("top_features", [])), record.get("observation_cutoff"),
                    record["generated_at"], record.get("status", "READY"), json.dumps(record.get("limitations", [])),
                    provenance.get("model_sha256"), provenance.get("metadata_sha256"), record.get("created_at", record["generated_at"]),
                )
            record["id"] = str(assessment_id)
            return record
        except asyncpg.PostgresError as exc:
            from .persistence import DatabaseError
            raise DatabaseError("ML wallet assessment could not be persisted") from exc

    async def persist_ml_inference(self, record):
        """Compatibility name for existing service wiring; still targets the new table."""
        return await self.create_assessment(record)

    async def list_case_assessments(self, case_id: str, limit: int = 50):
        return await self._list_assessments("case_id=$1", UUID(case_id), limit=limit)

    async def get_latest_wallet_assessment(self, chain: str, address: str):
        rows = await self._list_assessments("chain=$1 AND normalized_address=$2", chain, address.lower() if chain == "ethereum" else address, limit=1)
        return rows[0] if rows else None

    async def get_latest_case_assessment(self, case_id: str):
        rows = await self._list_assessments("case_id=$1", UUID(case_id), limit=1)
        return rows[0] if rows else None

    async def ml_inferences(self, case_id: str | None = None, chain: str | None = None, address: str | None = None, limit: int = 50):
        clauses = []; values = []
        if case_id: values.append(UUID(case_id)); clauses.append(f"case_id=${len(values)}")
        if chain: values.append(chain); clauses.append(f"chain=${len(values)}")
        if address: values.append(address.lower() if chain == "ethereum" else address); clauses.append(f"normalized_address=${len(values)}")
        return await self._list_assessments(" AND ".join(clauses) or "TRUE", *values, limit=limit)

    async def _list_assessments(self, predicate: str, *args, limit: int = 50):
        try:
            async with self._require_pool().acquire() as conn:
                rows = await conn.fetch(f"SELECT * FROM ml_wallet_assessments WHERE {predicate} ORDER BY generated_at DESC LIMIT ${len(args)+1}", *args, limit)
            result = []
            for row in rows:
                item = dict(row)
                item["id"] = str(item["id"]); item["inference_id"] = item["id"]; item["case_id"] = str(item["case_id"]); item["wallet_id"] = str(item["wallet_id"]) if item.get("wallet_id") else None
                for source, target, default in (("features_json", "features", {}), ("top_features_json", "top_features", []), ("limitations_json", "limitations", [])):
                    value = item.get(source, default); item[target] = json.loads(value) if isinstance(value, str) else (value or default)
                item["provenance"] = {"model_sha256": item.get("model_sha256"), "metadata_sha256": item.get("metadata_sha256")}
                result.append(item)
            return result
        except (asyncpg.PostgresError, ValueError) as exc:
            from .persistence import DatabaseError
            raise DatabaseError("ML wallet assessments could not be retrieved") from exc
