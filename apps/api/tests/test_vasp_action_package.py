from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from app.domain import Chain, ConfidenceLevel, EntityType, VaspCandidate
from app.vasp_action_package import VaspActionPackageService

class Repo:
    def __init__(self, candidate):
        self.candidate = candidate; self.saved = []
        self.case = SimpleNamespace(case_id="case-1", external_case_reference="SRC-1", latest_trace=SimpleNamespace(trace_id="trace-1", root_address="0x"+"a"*40, edges=[SimpleNamespace(transaction_hash="tx-1", source="0x"+"a"*40, destination="0x"+"b"*40)]))
    async def get(self, case_id): return self.case
    async def cross_chain_links(self, case_id): return []
    async def persist_vasp_action_package(self, package): self.saved.append(package); return package

class Reports:
    async def generate(self, *args, **kwargs): return SimpleNamespace(report_id="report-1", manifest_id="manifest-1", manifest_hash="hash-1", assessment_id="risk-1", pattern_ids=["pattern-1"], evidence_ids=["e-1"], sections={"risk": {}, "recommendations": []})

class Evidence:
    async def create_manifest(self, *args, **kwargs): return SimpleNamespace(manifest_id="manifest-1", content_hash="hash-1")

def candidate(entity_id="vasp-1"):
    return VaspCandidate(rank=1, entity_id=entity_id, entity_name="Example VASP", entity_type=EntityType.VASP, address="0x"+"b"*40, chain=Chain.ETHEREUM, hop_distance=1, observed_linked_amount="10 ETH", observed_asset="ETH", attribution_confidence=ConfidenceLevel.HIGH, attribution_source="dataset", source_version="v1", source_reference="ref-1", evidence_path=["tx-1"], transaction_hashes=["tx-1"], evidence_ids=["e-1"], classification="PROBABLE")

@pytest.mark.asyncio
async def test_package_preserves_ordered_path_and_integrity():
    repo = Repo(candidate()); result = await VaspActionPackageService(repo, Reports(), Evidence(), lambda trace: _one()).generate("case-1")
    assert result.transaction_hashes == ["tx-1"]
    assert result.fund_flow["complete_evidence_path"] == ["tx-1"]
    assert result.evidence["evidence_ids"] == ["e-1"]
    assert len(result.integrity_hash) == 64
    assert result.recommended_next_step == "Investigator review recommended for appropriate VASP coordination."

@pytest.mark.asyncio
async def test_unresolved_vasp_blocks_package():
    repo = Repo(None)
    with pytest.raises(LookupError, match="VASP_UNRESOLVED"):
        await VaspActionPackageService(repo, Reports(), Evidence(), lambda trace: _none()).generate("case-1")

def _one(): return [candidate()]
def _none(): return []
