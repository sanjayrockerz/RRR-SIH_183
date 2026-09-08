from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.domain import (
    AddressAttribution,
    AttributionRole,
    Chain,
    ConfidenceLevel,
    Evidence,
    InvestigationCase,
    InvestigationWorkflowState,
    InvestigatorRecommendation,
    InvestigativePriority,
    PatternObservation,
    PipelineStage,
    ProvenanceType,
    RiskAssessment,
    RiskBand,
    RiskSubject,
    TraceResult,
    VaspActionPackage,
    WalletCreate,
    WorkflowStageStatus,
)
from app.investigation_orchestrator import (
    InvestigationOrchestrator,
    InvestigatorRecommendationEngine,
    VaspActionabilityEngine,
)

import app.main as main_module
from app.main import app
from app.memory_repository import MemoryCaseRepository


@pytest.fixture(autouse=True)
def setup_memory_repo():
    memory_repo = MemoryCaseRepository()
    main_module.repo = memory_repo
    main_module.pattern_service.repository = memory_repo
    main_module.risk_service.repository = memory_repo
    main_module.alert_service.repository = memory_repo
    main_module.evidence_service.repository = memory_repo
    main_module.report_service.repository = memory_repo
    main_module.cross_chain_service.repository = memory_repo
    main_module.realtime_service.repository = memory_repo
    main_module.investigation_orchestrator.repository = memory_repo
    return memory_repo


@pytest.mark.asyncio
async def test_vasp_actionability_engine_ranking_and_provenance():
    engine = VaspActionabilityEngine()
    attr = AddressAttribution(
        attribution_id="attr-1",
        chain=Chain.ETHEREUM,
        address="0x1111111111111111111111111111111111111111",
        entity_id="Binance",
        role=AttributionRole.DEPOSIT,
        confidence=ConfidenceLevel.HIGH,
        source_id="OFAC_ATTRIBUTION",
        source_reference="Ref-123",
        evidence_id="ev-attr-1",
    )

    candidates, action_package = engine.evaluate_actionability(
        trace_result=None,
        attributions=[attr],
        case_id="case-demo",
        source_wallet="0x1111111111111111111111111111111111111111",
    )

    assert len(candidates) >= 1
    top = candidates[0]
    assert top.vasp_name == "Binance"
    assert top.provenance == ProvenanceType.ATTRIBUTED
    assert top.score >= 80.0
    assert action_package is not None
    assert action_package.probable_vasp == "Binance"
    assert action_package.confidence == ConfidenceLevel.HIGH


@pytest.mark.asyncio
async def test_investigator_recommendation_engine_rule_evaluations():
    now = datetime.now(timezone.utc)
    engine = InvestigatorRecommendationEngine()
    case = InvestigationCase(
        case_id="case-rec",
        title="Test Case",
        fraud_type="PIG_BUTCHERING",
        priority="HIGH",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address="0x1111111111111111111111111111111111111111", chain=Chain.ETHEREUM)],
    )
    vasp_pkg = VaspActionPackage(
        case_reference="case-rec",
        source_wallet="0x1111111111111111111111111111111111111111",
        probable_vasp="Coinbase",
        linked_value=50000.0,
        confidence=ConfidenceLevel.HIGH,
        evidence_ids=["ev-1"],
    )
    risk = RiskAssessment(
        assessment_id="risk-1",
        case_id="case-rec",
        trace_id="trace-rec",
        subject=RiskSubject(
            subject_id="subj-1",
            case_id="case-rec",
            chain=Chain.ETHEREUM,
            address="0x1111111111111111111111111111111111111111",
        ),
        version=1,
        score=85.0,
        band=RiskBand.CRITICAL,
        priority=InvestigativePriority.CRITICAL,
        priority_reason="High risk score",
        calculation_version="1.0",
        calculated_at=now,
        explanation="High risk test",
    )

    recs = engine.generate_recommendations(
        case=case,
        risk=risk,
        vasp_package=vasp_pkg,
    )

    assert len(recs) >= 2
    priorities = [r.priority for r in recs]
    assert "CRITICAL" in priorities
    actions = [r.recommendation for r in recs]
    assert any("Coinbase" in a for a in actions)
    assert any("Freeze" in a for a in actions)


@pytest.mark.asyncio
async def test_investigation_orchestrator_pipeline_execution(setup_memory_repo):
    repo = setup_memory_repo
    now = datetime.now(timezone.utc)
    case = InvestigationCase(
        case_id="case-pipeline",
        title="Pipeline Test Case",
        fraud_type="INVESTMENT_FRAUD",
        priority="HIGH",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address="0x1111111111111111111111111111111111111111", chain=Chain.ETHEREUM)],
    )
    repo._cases[case.case_id] = case

    orchestrator = InvestigationOrchestrator(repository=repo)
    wf_state = await orchestrator.run_pipeline(case.case_id)

    assert wf_state.case_id == "case-pipeline"
    assert wf_state.status == WorkflowStageStatus.COMPLETED
    assert len(wf_state.stages) == 9
    assert all(s.status == WorkflowStageStatus.COMPLETED for s in wf_state.stages)
    assert wf_state.vasp_action_package is not None
    assert len(wf_state.recommendations) > 0


@pytest.mark.asyncio
async def test_investigation_orchestrator_retry_stage(setup_memory_repo):
    repo = setup_memory_repo
    now = datetime.now(timezone.utc)
    case = InvestigationCase(
        case_id="case-retry",
        title="Retry Test Case",
        fraud_type="INVESTMENT_FRAUD",
        priority="HIGH",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address="0x1111111111111111111111111111111111111111", chain=Chain.ETHEREUM)],
    )
    repo._cases[case.case_id] = case

    orchestrator = InvestigationOrchestrator(repository=repo)
    await orchestrator.run_pipeline(case.case_id)

    # Retry TRACE stage
    updated_wf = await orchestrator.retry_stage(case.case_id, PipelineStage.TRACE)
    trace_stage = next(s for s in updated_wf.stages if s.stage == PipelineStage.TRACE)
    assert trace_stage.status == WorkflowStageStatus.COMPLETED


def test_investigation_rest_endpoints():
    with TestClient(app) as client:
        # Seed demo case first
        seed_res = client.post("/api/v1/dev/seed-case")
        assert seed_res.status_code == 200
        case_data = seed_res.json()
        case_id = case_data.get("case_id") or "case-1"

        # POST /api/v1/cases/{case_id}/investigate
        inv_res = client.post(f"/api/v1/cases/{case_id}/investigate")
        assert inv_res.status_code == 200
        inv_body = inv_res.json()
        assert inv_body["case_id"] == case_id
        assert "workflow" in inv_body

        # GET /api/v1/cases/{case_id}/workflow
        wf_res = client.get(f"/api/v1/cases/{case_id}/workflow")
        assert wf_res.status_code == 200
        wf_body = wf_res.json()
        assert wf_body["case_id"] == case_id
        assert len(wf_body["stages"]) == 9

        # POST /api/v1/cases/{case_id}/workflow/{stage}/retry
        retry_res = client.post(f"/api/v1/cases/{case_id}/workflow/VASP_ATTRIBUTION/retry")
        assert retry_res.status_code == 200
        retry_body = retry_res.json()
        assert retry_body["case_id"] == case_id
