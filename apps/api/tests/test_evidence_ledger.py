from datetime import datetime, timezone
import pytest

from app.domain import Chain, Evidence, EvidenceManifestRequest
from app.evidence_ledger import EvidenceLedgerService
from app.evidence_service import EvidenceService


def evidence(evidence_id="e-1"):
    return Evidence(evidence_id=evidence_id, case_id="case-1", type="TRANSACTION", chain=Chain.ETHEREUM, tx_hash="0x"+"a"*64, source="fixture", captured_at=datetime(2026,1,1,tzinfo=timezone.utc), metadata={"block":16})


def test_content_hash_is_stable_and_sensitive_to_observation_content():
    ledger=EvidenceLedgerService(); first=ledger.content_hash(evidence()); second=ledger.content_hash(evidence())
    assert first == second
    changed=evidence().model_copy(update={"metadata":{"block":17}})
    assert first != ledger.content_hash(changed)


def test_manifest_order_is_deterministic():
    ledger=EvidenceLedgerService(); items=[evidence("e-2"),evidence("e-1")]
    one=ledger.manifest("case-1",items,EvidenceManifestRequest()); two=ledger.manifest("case-1",list(reversed(items)),EvidenceManifestRequest())
    assert one.content_hash == two.content_hash
    assert one.evidence_ids == ["e-1","e-2"]


class Repo:
    def __init__(self): self.items=[evidence()]; self.manifest=None; self.events=[]
    async def get(self,case_id): return object()
    async def list_evidence(self,case_id): return self.items
    async def persist_evidence_manifest(self,manifest,evidence,events): self.manifest=manifest; self.events=events; return manifest
    async def append_audit_event(self,event): self.events.append(event)
    async def append_timeline(self,event): self.events.append(event)


@pytest.mark.asyncio
async def test_manifest_service_hashes_items_and_records_chain_event():
    repo=Repo(); result=await EvidenceService(repo).create_manifest("case-1",EvidenceManifestRequest(created_by="investigator"))
    assert result.evidence_count == 1
    assert repo.events[0].event_type == "MANIFESTED"
    assert repo.events[0].metadata["content_hash"]
