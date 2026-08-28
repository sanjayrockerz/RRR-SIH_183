from uuid import UUID
import json
import asyncpg

from .domain import Evidence, EvidenceChainEvent, EvidenceLedgerEntry, EvidenceManifest, EvidenceManifestRequest


class EvidencePersistenceMixin:
    def _evidence_from_row(self, row):
        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
        return Evidence(evidence_id=str(row["evidence_id"]), case_id=str(row["case_id"]), type=row["evidence_type"], chain=row["chain"], tx_hash=row["tx_hash"], source=row["source"], captured_at=row["captured_at"], metadata=metadata, content_hash=row.get("content_hash"), integrity_status=row.get("integrity_status") or "UNVERIFIED")

    async def list_all_evidence(self) -> list[Evidence]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows = await conn.fetch("SELECT * FROM evidence ORDER BY captured_at DESC")
            return [self._evidence_from_row(row) for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Evidence could not be retrieved") from exc

    async def get_evidence(self, evidence_id: str) -> Evidence | None:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM evidence WHERE evidence_id=$1", UUID(evidence_id))
            return self._evidence_from_row(row) if row else None
        except (asyncpg.PostgresError, ValueError) as exc:
            raise DatabaseError("Evidence could not be retrieved") from exc

    async def persist_evidence_manifest(self, manifest: EvidenceManifest, evidence: list[Evidence], events: list[EvidenceChainEvent]) -> EvidenceManifest:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1", UUID(manifest.case_id)): raise ValueError("Case not found")
                    await conn.execute("INSERT INTO evidence_manifests(manifest_id,case_id,algorithm,content_hash,evidence_count,created_at,created_by) VALUES($1,$2,$3,$4,$5,$6,$7)", UUID(manifest.manifest_id), UUID(manifest.case_id), manifest.algorithm, manifest.content_hash, manifest.evidence_count, manifest.created_at, manifest.created_by)
                    for item in evidence:
                        if item.case_id != manifest.case_id: raise ValueError("Evidence does not belong to case")
                        item_hash = item.content_hash
                        if not item_hash: raise ValueError("Evidence content hash is required")
                        await conn.execute("UPDATE evidence SET content_hash=$2,integrity_status='HASHED' WHERE evidence_id=$1 AND case_id=$3", UUID(item.evidence_id), item_hash, UUID(manifest.case_id))
                        await conn.execute("INSERT INTO evidence_manifest_items(manifest_id,evidence_id,content_hash) VALUES($1,$2,$3)", UUID(manifest.manifest_id), UUID(item.evidence_id), item_hash)
                    for event in events:
                        await conn.execute("INSERT INTO evidence_chain_events(event_id,evidence_id,case_id,event_type,actor_id,occurred_at,previous_hash,event_hash,metadata) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)", UUID(event.event_id), UUID(event.evidence_id), UUID(event.case_id), event.event_type, event.actor_id, event.occurred_at, event.previous_hash, event.event_hash, json.dumps(event.metadata))
            return manifest
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Evidence manifest could not be persisted") from exc

    async def evidence_ledger(self, case_id: str) -> list[EvidenceLedgerEntry]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                evidence_rows=await conn.fetch("SELECT * FROM evidence WHERE case_id=$1 ORDER BY created_at", UUID(case_id))
                result=[]
                for row in evidence_rows:
                    evidence=self._evidence_from_row(row)
                    events=await conn.fetch("SELECT * FROM evidence_chain_events WHERE case_id=$1 AND evidence_id=$2 ORDER BY occurred_at",UUID(case_id),UUID(evidence.evidence_id))
                    manifests=await conn.fetch("SELECT manifest_id FROM evidence_manifest_items WHERE evidence_id=$1 ORDER BY manifest_id",UUID(evidence.evidence_id))
                    result.append(EvidenceLedgerEntry(evidence=evidence,chain_of_custody=[EvidenceChainEvent(event_id=str(item["event_id"]),evidence_id=str(item["evidence_id"]),case_id=str(item["case_id"]),event_type=item["event_type"],actor_id=item["actor_id"],occurred_at=item["occurred_at"],previous_hash=item["previous_hash"],event_hash=item["event_hash"],metadata=json.loads(item["metadata"]) if isinstance(item["metadata"],str) else (item["metadata"] or {})) for item in events],manifest_ids=[str(item["manifest_id"]) for item in manifests]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Evidence ledger could not be retrieved") from exc

    async def evidence_manifests(self, case_id: str) -> list[EvidenceManifest]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT * FROM evidence_manifests WHERE case_id=$1 ORDER BY created_at DESC",UUID(case_id))
                result=[]
                for row in rows:
                    items=await conn.fetch("SELECT evidence_id FROM evidence_manifest_items WHERE manifest_id=$1 ORDER BY evidence_id",row["manifest_id"])
                    result.append(EvidenceManifest(manifest_id=str(row["manifest_id"]),case_id=str(row["case_id"]),algorithm=row["algorithm"],content_hash=row["content_hash"],evidence_ids=[str(item["evidence_id"]) for item in items],evidence_count=row["evidence_count"],created_at=row["created_at"],created_by=row["created_by"]))
                return result
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Evidence manifests could not be retrieved") from exc

    async def evidence_chain(self, case_id: str, evidence_id: str) -> list[EvidenceChainEvent]:
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT * FROM evidence_chain_events WHERE case_id=$1 AND evidence_id=$2 ORDER BY occurred_at",UUID(case_id),UUID(evidence_id))
            return [EvidenceChainEvent(event_id=str(row["event_id"]),evidence_id=str(row["evidence_id"]),case_id=str(row["case_id"]),event_type=row["event_type"],actor_id=row["actor_id"],occurred_at=row["occurred_at"],previous_hash=row["previous_hash"],event_hash=row["event_hash"],metadata=json.loads(row["metadata"]) if isinstance(row["metadata"],str) else (row["metadata"] or {})) for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc: raise DatabaseError("Evidence chain of custody could not be retrieved") from exc
