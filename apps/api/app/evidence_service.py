from datetime import datetime, timezone
from uuid import uuid4

from .domain import AuditEvent, EvidenceChainEvent, EvidenceManifestRequest, TimelineEvent
from .evidence_ledger import EvidenceLedgerService


class EvidenceService:
    def __init__(self, repository, ledger: EvidenceLedgerService | None = None):
        self.repository = repository
        self.ledger = ledger or EvidenceLedgerService()

    async def create_manifest(self, case_id: str, request: EvidenceManifestRequest):
        if not await self.repository.get(case_id): raise ValueError("Case not found")
        evidence = await self.repository.list_evidence(case_id)
        if request.evidence_ids and not set(request.evidence_ids).issubset({item.evidence_id for item in evidence}): raise ValueError("One or more evidence records were not found in this case")
        manifest = self.ledger.manifest(case_id, evidence, request)
        if not manifest.evidence_ids: raise ValueError("At least one evidence record is required")
        hashed = [item.model_copy(update={"content_hash": self.ledger.content_hash(item)}) for item in evidence if item.evidence_id in set(manifest.evidence_ids)]
        events = [self.ledger.chain_event(item, "MANIFESTED", actor_id=request.created_by, metadata={"manifest_id": manifest.manifest_id, "content_hash": item.content_hash}) for item in hashed]
        result = await self.repository.persist_evidence_manifest(manifest, hashed, events)
        now=datetime.now(timezone.utc)
        await self.repository.append_audit_event(AuditEvent(event_id=str(uuid4()),case_id=case_id,action="EVIDENCE_MANIFEST_CREATED",resource_type="EVIDENCE_MANIFEST",resource_id=result.manifest_id,actor_id=request.created_by,occurred_at=now,metadata={"evidence_count":result.evidence_count,"algorithm":result.algorithm}))
        await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case_id,timestamp=now,event_type="EVIDENCE_MANIFEST_CREATED",summary=f"Evidence manifest created for {result.evidence_count} persisted observation(s).",source="EvidenceLedger",evidence_ids=result.evidence_ids,metadata={"manifest_id":result.manifest_id,"content_hash":result.content_hash}))
        return result

    async def ledger_entries(self, case_id: str): return await self.repository.evidence_ledger(case_id)
    async def manifests(self, case_id: str): return await self.repository.evidence_manifests(case_id)
    async def chain(self, case_id: str, evidence_id: str): return await self.repository.evidence_chain(case_id, evidence_id)
