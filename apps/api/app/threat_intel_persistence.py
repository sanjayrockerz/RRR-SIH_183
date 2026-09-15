from uuid import UUID

from .threat_intel.schemas import ThreatIntelObservation


class ThreatIntelPersistenceMixin:
    async def persist_threat_intel(self, observation: ThreatIntelObservation) -> ThreatIntelObservation:
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute(
                    """INSERT INTO threat_intel_observations
                    (observation_id,chain,address,source,source_version,indicator,match_type,confidence,reference,retrieved_at,raw_status,case_id,created_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                    UUID(observation.observation_id), observation.chain.value, observation.address,
                    observation.source, observation.source_version, observation.indicator,
                    observation.match_type.value, observation.confidence, observation.reference,
                    observation.retrieved_at, observation.raw_status.value,
                    UUID(observation.case_id) if observation.case_id else None, observation.created_at,
                )
            return observation
        except Exception as exc:
            import asyncpg
            if isinstance(exc, (asyncpg.PostgresError, ValueError)):
                from .persistence import DatabaseError
                raise DatabaseError("Threat intelligence observation could not be persisted") from exc
            raise

    async def threat_intel_observations(self, chain=None, address=None, case_id=None) -> list[ThreatIntelObservation]:
        try:
            clauses, args = [], []
            if chain is not None:
                args.append(chain.value if hasattr(chain, "value") else chain)
                clauses.append(f"chain=${len(args)}")
            if address is not None:
                args.append(address)
                clauses.append(f"address=${len(args)}")
            if case_id is not None:
                args.append(UUID(case_id))
                clauses.append(f"case_id=${len(args)}")
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            async with self._require_pool().acquire() as conn:
                rows = await conn.fetch("SELECT * FROM threat_intel_observations" + where + " ORDER BY retrieved_at DESC, created_at DESC", *args)
            return [ThreatIntelObservation(
                observation_id=str(row["observation_id"]), chain=row["chain"], address=row["address"],
                source=row["source"], source_version=row["source_version"], indicator=row["indicator"],
                match_type=row["match_type"], confidence=row["confidence"], reference=row["reference"],
                retrieved_at=row["retrieved_at"], raw_status=row["raw_status"],
                case_id=str(row["case_id"]) if row["case_id"] else None, created_at=row["created_at"],
            ) for row in rows]
        except Exception as exc:
            import asyncpg
            if isinstance(exc, (asyncpg.PostgresError, ValueError)):
                from .persistence import DatabaseError
                raise DatabaseError("Threat intelligence observations could not be retrieved") from exc
            raise
