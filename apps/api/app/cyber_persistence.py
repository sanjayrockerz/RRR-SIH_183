from datetime import datetime, timezone
from uuid import UUID
import json
import asyncpg

from .domain import AddressScreeningResult, Chain, ContractSecurityFinding, IntelligenceConfidence, IntelligenceSource, IntelligenceSourceStatus, IndicatorType, SanctionsRecord, ScreeningMatch, ScreeningOutcome, ThreatIndicator


class CyberPersistenceMixin:
    async def intelligence_sources(self) -> list[IntelligenceSource]:
        from .persistence import DatabaseError
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM cyber_intelligence_sources ORDER BY name, dataset_version DESC")
            return [IntelligenceSource(source_id=str(r["source_id"]), name=r["name"], source_type=r["source_type"], publisher=r["publisher"], reference=r["reference"], dataset_version=r["dataset_version"], status=r["status"], retrieved_at=r["retrieved_at"], metadata=r["metadata"] or {}) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Cyber-intelligence sources could not be retrieved") from exc

    async def threat_indicators(self, chain: Chain | None = None) -> list[ThreatIndicator]:
        from .persistence import DatabaseError
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM threat_indicators WHERE ($1::text IS NULL OR chain=$1) ORDER BY normalized_value", chain)
            return [ThreatIndicator(indicator_id=str(r["indicator_id"]), source_id=str(r["source_id"]), indicator_type=r["indicator_type"], value=r["value"], normalized_value=r["normalized_value"], chain=r["chain"], confidence=r["confidence"], first_observed_at=r["first_observed_at"], last_observed_at=r["last_observed_at"], metadata=r["metadata"] or {}) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Threat indicators could not be retrieved") from exc

    async def contract_security_findings(self, chain: Chain, address: str) -> list[ContractSecurityFinding]:
        from .persistence import DatabaseError
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM contract_security_findings WHERE chain=$1 AND lower(contract_address)=lower($2) ORDER BY observed_at DESC", chain, address)
            return [ContractSecurityFinding(finding_id=str(r["finding_id"]), chain=r["chain"], contract_address=r["contract_address"], source_id=str(r["source_id"]), finding_type=r["finding_type"], severity=r["severity"], confidence=r["confidence"], description=r["description"], evidence_ids=json.loads(r["evidence_ids"]) if isinstance(r["evidence_ids"], str) else (r["evidence_ids"] or []), observed_at=r["observed_at"], metadata=r["metadata"] or {}) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Contract-security findings could not be retrieved") from exc

    async def sanctions_records(self) -> list[SanctionsRecord]:
        from .persistence import DatabaseError
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM sanctions_records ORDER BY normalized_value")
            return [SanctionsRecord(record_id=str(r["record_id"]), source_id=str(r["source_id"]), subject_type=r["subject_type"], value=r["value"], normalized_value=r["normalized_value"], chain=r["chain"], program=r["program"], listed_at=r["listed_at"], revoked_at=r["revoked_at"], confidence=r["confidence"], source_reference=r["source_reference"], dataset_version=r["dataset_version"], metadata=r["metadata"] or {}) for r in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Sanctions records could not be retrieved") from exc

    async def persist_screening(self, case_id: str | None, result: AddressScreeningResult) -> AddressScreeningResult:
        from .persistence import DatabaseError
        pool = self._require_pool(); screening_id = UUID(str(__import__("uuid").uuid4()))
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("INSERT INTO screening_runs(screening_id,case_id,chain,address,outcome,source_status,screened_at,explanation,limitation) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)", screening_id, UUID(case_id) if case_id else None, result.chain, result.address, result.outcome, result.source_status, result.screened_at, result.explanation, result.limitation)
                    for match in result.matches:
                        await conn.execute("INSERT INTO screening_matches(screening_id,match_id,record_id,source_id,matched_value,match_type,confidence,explanation,evidence_ids) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)", screening_id, UUID(match.match_id), UUID(match.record_id), UUID(match.source_id), match.matched_value, match.match_type, match.confidence, match.explanation, json.dumps(match.evidence_ids))
            return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Sanctions screening could not be persisted") from exc

    async def case_screenings(self, case_id: str) -> list[AddressScreeningResult]:
        from .persistence import DatabaseError
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM screening_runs WHERE case_id=$1 ORDER BY screened_at DESC", UUID(case_id))
                result = []
                for row in rows:
                    matches = await conn.fetch("SELECT * FROM screening_matches WHERE screening_id=$1", row["screening_id"])
                    result.append(AddressScreeningResult(chain=row["chain"], address=row["address"], outcome=row["outcome"], source_status=row["source_status"], screened_at=row["screened_at"], explanation=row["explanation"], limitation=row["limitation"], matches=[ScreeningMatch(match_id=str(m["match_id"]), record_id=str(m["record_id"]), source_id=str(m["source_id"]), matched_value=m["matched_value"], match_type=m["match_type"], confidence=m["confidence"], explanation=m["explanation"], evidence_ids=json.loads(m["evidence_ids"]) if isinstance(m["evidence_ids"], str) else (m["evidence_ids"] or [])) for m in matches]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Screening results could not be retrieved") from exc

    async def sync_sanctions_records(self, dataset_version: str, source: str, records: list[SanctionsRecord]):
        from .persistence import DatabaseError
        import hashlib
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        source_id = UUID(str(__import__("uuid").uuid4()))
        checksum = hashlib.sha256(json.dumps([r.model_dump() for r in records], default=str).encode('utf-8')).hexdigest()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        INSERT INTO cyber_intelligence_sources(source_id, name, source_type, reference, dataset_version, status, retrieved_at, metadata, created_at, updated_at)
                        VALUES($1, 'OFAC', 'SANCTIONS', $2, $3, 'CONFIGURED', $4, $5, $4, $4)
                        ON CONFLICT(name, dataset_version) DO UPDATE SET updated_at=$4, status='CONFIGURED', metadata=$5
                    """, source_id, source, dataset_version, now, json.dumps({"checksum": checksum, "record_count": len(records)}))
                    
                    actual_source_id = await conn.fetchval("SELECT source_id FROM cyber_intelligence_sources WHERE name='OFAC' AND dataset_version=$1", dataset_version)
                    await conn.execute("DELETE FROM sanctions_records WHERE source_id=$1", actual_source_id)
                    
                    for r in records:
                        await conn.execute("""
                            INSERT INTO sanctions_records(record_id, source_id, subject_type, value, normalized_value, chain, program, listed_at, revoked_at, confidence, source_reference, dataset_version, metadata)
                            VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                            ON CONFLICT DO NOTHING
                        """, UUID(str(r.record_id)), actual_source_id, r.subject_type.value, r.value, r.normalized_value, r.chain.value if r.chain else None, r.program, r.listed_at, r.revoked_at, r.confidence.value, r.source_reference, dataset_version, json.dumps(r.metadata))
            return {
                "dataset_version": dataset_version,
                "source": source,
                "retrieved_at": now.isoformat(),
                "record_count": len(records),
                "checksum": checksum
            }
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Sanctions sync failed") from exc
