from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from .domain import Evidence, EvidenceChainEvent, EvidenceManifest, EvidenceManifestRequest


class EvidenceLedgerService:
    """Builds deterministic manifests without mutating original observations."""

    algorithm = "SHA-256"

    @staticmethod
    def content_hash(evidence: Evidence) -> str:
        payload = {
            "evidence_id": evidence.evidence_id,
            "case_id": evidence.case_id,
            "type": evidence.type,
            "chain": evidence.chain.value,
            "tx_hash": evidence.tx_hash,
            "source": evidence.source,
            "captured_at": evidence.captured_at.isoformat(),
            "metadata": evidence.metadata,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def manifest(self, case_id: str, evidence: list[Evidence], request: EvidenceManifestRequest) -> EvidenceManifest:
        selected = evidence if not request.evidence_ids else [item for item in evidence if item.evidence_id in set(request.evidence_ids)]
        selected = sorted(selected, key=lambda item: item.evidence_id)
        entries = [{"evidence_id": item.evidence_id, "content_hash": self.content_hash(item)} for item in sorted(selected, key=lambda item: item.evidence_id)]
        root = sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return EvidenceManifest(manifest_id=str(uuid4()), case_id=case_id, algorithm=self.algorithm, content_hash=root, evidence_ids=[item.evidence_id for item in selected], evidence_count=len(selected), created_at=datetime.now(timezone.utc), created_by=request.created_by)

    def chain_event(self, evidence: Evidence, event_type: str, previous_hash: str | None = None, actor_id: str | None = None, metadata: dict | None = None) -> EvidenceChainEvent:
        occurred_at = datetime.now(timezone.utc)
        body = {"evidence_id": evidence.evidence_id, "event_type": event_type, "occurred_at": occurred_at.isoformat(), "previous_hash": previous_hash, "metadata": metadata or {}}
        event_hash = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return EvidenceChainEvent(event_id=str(uuid4()), evidence_id=evidence.evidence_id, case_id=evidence.case_id, event_type=event_type, actor_id=actor_id, occurred_at=occurred_at, previous_hash=previous_hash, event_hash=event_hash, metadata=metadata or {})
