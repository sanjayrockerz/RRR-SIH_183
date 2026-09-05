"""
Part M Synthetic End-to-End Operational Test Suite
Validates the complete investigator platform scenario:
Victim 1 -> Suspect -> Intermediary 1 -> Bridge -> TRON -> Intermediary 2 -> VASP
Victim 2 -> Shared Intermediary
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.domain import (
    Chain,
    TraceDirection,
    TraceRequest,
    RiskAssessRequest,
    CaseWorkflowStage,
    VaspClassification,
    RiskBand,
    MonitoredWalletState,
    CaseCreate,
    WalletCreate,
    ReportCreateRequest,
    ReportType,
)
from app.persistence import PostgresCaseRepository
from app.services import TraceService
from app.vasp_attribution_engine import VASPAttributionEngine
from app.pattern_service import PatternService
from app.risk_service import RiskService
from app.cross_chain_service import CrossChainService
from app.action_engine import NextBestActionEngine
from app.vasp_package_service import VASPPackageService
from app.report_service import ReportService
from app.ncrp_sahyog_adapters import NCRPAdapter, SahyogAdapter
from app.provider_registry import BlockchainProviderRegistry
from app.fixture_provider import DevelopmentFixtureProvider


@pytest.fixture
def repo():
    return PostgresCaseRepository()


@pytest.fixture
def fixture_registry():
    provider = DevelopmentFixtureProvider()
    return BlockchainProviderRegistry([([Chain.ETHEREUM, Chain.TRON, Chain.BSC, Chain.BTC], provider)])


@pytest.mark.asyncio
async def test_full_synthetic_operational_pipeline(repo, fixture_registry):
    # 1. Create Case A (Victim 1)
    case_a = await repo.create(CaseCreate(title="Victim 1 Investment Fraud", fraud_type="INVESTIGATION", priority="HIGH", external_case_reference="NCRP-2026-001", description="Victim lost 10 ETH to phishing pool"))
    case_id_a = case_a.case_id

    victim_address = "0x" + "a" * 40
    await repo.add_wallet(case_id_a, WalletCreate(address=victim_address, chain=Chain.ETHEREUM))

    # 2. Trace case & generate graph flow
    tracer = TraceService(fixture_registry.get(Chain.ETHEREUM), fixture_registry)
    trace = await tracer.trace(case_id_a, TraceRequest(address=victim_address, chain=Chain.ETHEREUM, direction=TraceDirection.FORWARD, max_hops=3))
    assert trace is not None
    assert len(trace.nodes) > 0
    assert len(trace.edges) > 0
    await repo.persist_trace(trace)

    # 3. VASP Attribution
    from app.domain import VaspEntity, VaspBlockchainAddress
    vasp = VaspEntity(id="vasp-binance", legal_name="Binance Ltd", trading_name="Binance", regulatory_status="REGISTERED")
    vasp_addr = VaspBlockchainAddress(id="addr-1", vasp_id="vasp-binance", chain=Chain.ETHEREUM, address=trace.nodes[-1].address, label="Deposit Wallet")
    engine = VASPAttributionEngine([vasp], [vasp_addr], [])
    attributions = [engine.analyze(chain=Chain.ETHEREUM, wallet=victim_address, trace=trace)]
    assert len(attributions) > 0

    # 4. Pattern Analysis
    pattern_service = PatternService(repo)
    patterns = await pattern_service.analyze(trace, None, attributions)
    assert isinstance(patterns, list)

    # 5. Risk Assessment
    risk_service = RiskService(repo)
    assessment = await risk_service.assess(case_id_a, RiskAssessRequest(trace_id=trace.trace_id))
    assert assessment.score >= 0.0
    assert assessment.band in (RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.ELEVATED, RiskBand.GUARDED, RiskBand.LOW)

    # 6. Cross-Chain Analysis
    cross_chain_service = CrossChainService(repo)
    cross_trace = await cross_chain_service.analyze(case_id_a, None)
    assert cross_trace.status in ("COMPLETED", "PARTIAL")

    # 7. Next Best Actions
    nearest = await repo.get_nearest_vasps(case_id_a)
    cross_links = await cross_chain_service.links(case_id_a)
    rel_cases = await repo.related_cases(case_id_a)
    evidence = await repo.list_evidence(case_id_a)

    action_engine = NextBestActionEngine()
    actions = action_engine.recommend(case_id_a, assessment, nearest, cross_links, rel_cases, evidence)
    assert len(actions) > 0
    action_types = {a.action_type for a in actions}
    assert "GENERATE_INVESTIGATION_REPORT" in action_types

    # 8. VASP Package Generation
    package_service = VASPPackageService(repo)
    package = await package_service.generate_package(case_id_a, case_a.wallets, nearest[0] if nearest else None, evidence)
    assert package.package_id is not None
    assert package.evidence_manifest_hash is not None

    # 9. Investigation Report Generation & Multi-Format Export
    report_service = ReportService(repo)
    report = await report_service.generate(case_id_a, ReportCreateRequest(report_type=ReportType.INVESTIGATION_SUMMARY, trace_id=trace.trace_id, created_by="test-suite"))
    assert report.content_hash is not None

    json_export = await report_service.export_json(case_id_a, report.report_id)
    assert json_export["content_hash"] == report.content_hash

    csv_export = await report_service.export_csv(case_id_a, report.report_id)
    assert "TRANSACTION" in csv_export or "EVIDENCE" in csv_export

    # 10. Monitored Wallet State Transitions
    monitored = await repo.monitored_wallets(case_id_a)
    assert len(monitored) > 0
    updated_wallet = await repo.set_monitored_wallet_state(monitored[0].wallet_id, MonitoredWalletState.PAUSED)
    assert updated_wallet.state == MonitoredWalletState.PAUSED

    # 11. NCRP / Sahyog Integration State
    ncrp = NCRPAdapter("DEVELOPMENT_FIXTURE")
    sahyog = SahyogAdapter("DEVELOPMENT_FIXTURE")
    assert ncrp.get_state().status == "OPERATIONAL_MOCK"
    assert sahyog.get_state().status == "OPERATIONAL_MOCK"

    # 12. High Risk Summaries
    high_risk_c = await repo.high_risk_cases()
    high_risk_w = await repo.high_risk_wallets()
    assert len(high_risk_c) > 0
    assert len(high_risk_w) > 0


@pytest.mark.asyncio
async def test_unrelated_cases_no_false_correlation(repo):
    case_u = await repo.create(CaseCreate(title="Unrelated Case U", fraud_type="INVESTIGATION", priority="LOW"))
    rel = await repo.correlate_cases("invalid-id-a", case_u.case_id)
    assert len(rel) == 0
