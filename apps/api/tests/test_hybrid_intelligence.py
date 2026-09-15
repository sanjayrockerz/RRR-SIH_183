from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sys

import pytest

sys.path.insert(0, "apps/api")
from app.hybrid.rules import RULESET_VERSION, decide
from app.hybrid.schemas import HybridPriority
from app.hybrid.service import HybridInvestigationIntelligenceService


CASE_ID = "00000000-0000-0000-0000-000000000001"


class FakeRepository:
    def __init__(self):
        self.snapshots = []
        self.risk = SimpleNamespace(assessment_id="risk-1", band="HIGH", delta=SimpleNamespace(delta=0))
        self.ml = [{"inference_id": "ml-1", "probability": 0.91, "classification": "HIGH_RISK_LIKE", "threshold": 0.63, "model_version": "v2"}]
        self.patterns = [SimpleNamespace(pattern_id="pattern-1")]
        self.threat = []
        self.related = []
        self.cross = []
        self.events = []
        self.watches = [SimpleNamespace(status="ACTIVE")]
        self.registry = SimpleNamespace(record_id="registry-1", highest_investigative_risk_band="HIGH")
        self.case = SimpleNamespace(case_id=CASE_ID, wallets=[SimpleNamespace(chain="ETHEREUM", address="0x" + "1" * 40)], latest_trace=None)

    async def get(self, case_id): return self.case if case_id == CASE_ID else None
    async def latest_risk(self, case_id): return self.risk
    async def ml_inferences(self, **kwargs): return self.ml
    async def list_patterns(self, case_id): return self.patterns
    async def pattern_summary(self, case_id): return {"total_patterns": len(self.patterns)}
    async def threat_intel_observations(self, **kwargs): return self.threat
    async def related_cases(self, case_id): return self.related
    async def cross_chain_links(self, case_id): return self.cross
    async def list_watches(self, case_id): return self.watches
    async def list_realtime_events(self, case_id, limit=20): return self.events
    async def risk_registry_wallet(self, chain, address): return self.registry
    async def get_latest_hybrid_snapshot(self, case_id): return self.snapshots[-1] if self.snapshots else None
    async def persist_hybrid_snapshot(self, intelligence):
        if not any(x.state_hash == intelligence.state_hash for x in self.snapshots):
            self.snapshots.append(intelligence)
        return intelligence


@pytest.mark.asyncio
async def test_priority_rules_cover_p1_p2_p3():
    assert decide({"risk_band": "HIGH", "ml_high": True, "movement": True}).priority == HybridPriority.P1
    assert decide({"risk_band": "HIGH", "movement": False}).priority == HybridPriority.P2
    assert decide({"risk_band": "ELEVATED", "movement": False}).priority == HybridPriority.P3


@pytest.mark.asyncio
async def test_service_persists_evidence_and_deduplicates_identical_refreshes():
    repo = FakeRepository()
    service = HybridInvestigationIntelligenceService(repo)
    first = await service.build_case_intelligence(CASE_ID)
    second = await service.build_case_intelligence(CASE_ID)
    assert first.priority == HybridPriority.P2
    assert len(repo.snapshots) == 1
    assert {ref["id"] for ref in first.evidence_refs} >= {"risk-1", "ml-1", "pattern-1", "registry-1"}
    repo.events = [SimpleNamespace(event_id="event-1", observed_at=datetime.now(timezone.utc))]
    third = await service.build_case_intelligence(CASE_ID)
    assert third.priority == HybridPriority.P1
    assert third.priority_changed is True
    assert len(repo.snapshots) == 2
    assert second.state_hash == first.state_hash


@pytest.mark.asyncio
async def test_missing_ml_does_not_block_deterministic_path_and_inferred_cross_chain_is_limited():
    repo = FakeRepository()
    repo.ml = []
    repo.cross = [SimpleNamespace(link_id="cross-1", destination="TRON", observed_or_inferred="INFERRED")]
    result = await HybridInvestigationIntelligenceService(repo).build_case_intelligence(CASE_ID, persist=False)
    assert result.priority == HybridPriority.P2
    assert any("ML assessment is unavailable" in x for x in result.limitations)
    assert any("inferred correlation" in x for x in result.limitations)


@pytest.mark.asyncio
async def test_direct_match_and_probable_vasp_are_p1_without_criminality_claim():
    repo = FakeRepository()
    repo.risk = SimpleNamespace(assessment_id="risk-2", band="MEDIUM", delta=SimpleNamespace(delta=0))
    repo.threat = [SimpleNamespace(observation_id="threat-1", match_type="DIRECT_MATCH", raw_status="DIRECT_MATCH")]
    repo.case.latest_trace = SimpleNamespace(trace_id="trace-1")
    candidate = SimpleNamespace(entity_id="vasp-1", classification="PROBABLE", attribution_confidence="MEDIUM")
    async def resolve(_trace): return [candidate]
    result = await HybridInvestigationIntelligenceService(repo, resolve).build_case_intelligence(CASE_ID, persist=False)
    assert result.priority == HybridPriority.P1
    assert "CHAINABUSE_DIRECT_MATCH" in result.reason_codes
    assert "criminal group" not in " ".join(result.limitations).lower()


def test_frozen_artifact_hashes_unchanged():
    root = Path(__file__).resolve().parents[3]
    integrity = json.loads((root / "artifacts/ml_frozen_model_integrity.json").read_text())
    for key, expected in (("model_path", integrity["model_sha256"]), ("metadata_path", integrity["metadata_sha256"])):
        actual = hashlib.sha256((root / integrity[key]).read_bytes()).hexdigest()
        assert actual == expected
    assert integrity["status"] == "FROZEN_READ_ONLY"
