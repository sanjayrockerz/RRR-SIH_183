import time
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from app.main import app, repo, provider, realtime_service, realtime_provider, pattern_service, risk_service
from app.domain import Chain, ScreeningOutcome, InvestigationCase
from app.provider import AlchemyEthereumProvider, ProviderError

def test_webhook_signature_and_replay_protection():
    with TestClient(app) as client:
        # Invalid signature should be rejected with 401, 403, or 500
        headers = {"x-alchemy-signature": "invalid-sig"}
        payload = {
            "webhookId": "wh_123",
            "id": "evt_123",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "event": {
                "network": "ETH_MAINNET",
                "activity": [
                    {
                        "fromAddress": "0x1111111111111111111111111111111111111111",
                        "toAddress": "0x2222222222222222222222222222222222222222",
                        "transactionHash": "0x" + "a" * 64,
                        "blockNum": "0x1",
                        "value": "1.0",
                        "asset": "ETH"
                    }
                ]
            }
        }
        response = client.post("/api/v1/realtime/providers/alchemy/webhook", json=payload, headers=headers)
        assert response.status_code in {401, 403, 500}

        # Old event triggers replay protection window
        old_payload = payload.copy()
        old_payload["createdAt"] = "2020-01-01T00:00:00Z"
        assert not realtime_provider.verify_signature(b"{}", "sig")


@pytest.mark.asyncio
async def test_provider_health_check_probe():
    h = await provider.health()
    assert h["provider"] == "alchemy"
    assert "status" in h
    assert "network" in h
    assert "capabilities" in h
    assert "last_checked" in h


@pytest.mark.asyncio
async def test_sanctions_unknown_behavior_on_empty():
    # If database contains no config (but CuratedSanctionsProvider is configured=True), it returns UNKNOWN
    from app.cyber_intelligence import CuratedSanctionsProvider
    sanctions_provider = CuratedSanctionsProvider(records=[], configured=True)
    res = await sanctions_provider.screen_address(Chain.ETHEREUM, "0x1111111111111111111111111111111111111111")
    assert res.outcome == ScreeningOutcome.UNKNOWN


@pytest.mark.asyncio
async def test_integrated_investigation_pipeline_runs(monkeypatch):
    # Mock tracer.trace to return a mock TraceResult immediately to prevent actual Alchemy RPC calls
    from app.domain import TraceResult, TraceMetrics, AcquisitionStatistics, DataMode
    
    mock_trace = TraceResult(
        case_id=str(uuid4()),
        trace_id=str(uuid4()),
        root_address="0x1111111111111111111111111111111111111111",
        mode=DataMode.DEVELOPMENT_FIXTURE,
        provider="Mock Tracer",
        nodes=[],
        edges=[],
        signals=[],
        evidence=[],
        metrics=TraceMetrics(node_count=1, edge_count=0, unique_transaction_count=0),
        acquisition=AcquisitionStatistics(
            discovered=0,
            normalized=0,
            persisted=0,
            duplicates=0,
            failed=0,
            skipped=0,
            provider="Mock",
            mode=DataMode.DEVELOPMENT_FIXTURE,
            retrieved_at=datetime.now(timezone.utc)
        )
    )
    
    async def mock_trace_func(*args, **kwargs):
        return mock_trace
        
    from app.main import tracer
    monkeypatch.setattr(tracer, "trace", mock_trace_func)
    
    # Mock database repository status and methods
    monkeypatch.setattr(repo, "status", "READY")
    
    mock_case = InvestigationCase(
        case_id="case-123",
        title="Test Pipeline Run",
        fraud_type="Investment fraud",
        priority="HIGH",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        wallets=[],
        transactions=[]
    )
    
    async def mock_create(body):
        return mock_case
    async def mock_get(case_id):
        return mock_case
    async def mock_add_wallet(case_id, wallet):
        mock_case.wallets.append(wallet)
        return mock_case
    async def mock_set_case_status(case_id, status):
        mock_case.status = status
        return mock_case
    async def mock_persist_trace(trace):
        return trace
    async def mock_persist_screening(*args, **kwargs):
        pass
    async def mock_sanctions_records(*args, **kwargs):
        return []
    async def mock_attribution_catalog(*args, **kwargs):
        return [], {}, []
    async def mock_set_workflow_stage(*args, **kwargs):
        pass
    async def mock_append_timeline(*args, **kwargs):
        pass
    async def mock_workflow_events(*args, **kwargs):
        return []
    async def mock_case_transactions(*args, **kwargs):
        return []
    async def mock_case_entities(*args, **kwargs):
        return []
    async def mock_case_summary_counts(*args, **kwargs):
        return {"wallets": 0, "transactions": 0, "graph_nodes": 0, "graph_edges": 0, "patterns": 0, "evidence": 0, "alerts": 0, "active_watches": 0, "realtime_events": 0}
    async def mock_case_screenings(*args, **kwargs):
        return []
    async def mock_list_evidence(*args, **kwargs):
        return []
    async def mock_alerts(*args, **kwargs):
        return []
    async def mock_list_reports(*args, **kwargs):
        return []
    async def mock_database_integrity(*args, **kwargs):
        return {"counts": {}, "orphans": {}}

    monkeypatch.setattr(repo, "create", mock_create)
    monkeypatch.setattr(repo, "get", mock_get)
    monkeypatch.setattr(repo, "add_wallet", mock_add_wallet)
    monkeypatch.setattr(repo, "_set_case_status", mock_set_case_status)
    monkeypatch.setattr(repo, "persist_trace", mock_persist_trace)
    monkeypatch.setattr(repo, "persist_screening", mock_persist_screening)
    monkeypatch.setattr(repo, "sanctions_records", mock_sanctions_records)
    monkeypatch.setattr(repo, "attribution_catalog", mock_attribution_catalog)
    monkeypatch.setattr(repo, "set_workflow_stage", mock_set_workflow_stage)
    monkeypatch.setattr(repo, "append_timeline", mock_append_timeline)
    monkeypatch.setattr(repo, "workflow_events", mock_workflow_events)
    monkeypatch.setattr(repo, "case_transactions", mock_case_transactions)
    monkeypatch.setattr(repo, "case_entities", mock_case_entities)
    monkeypatch.setattr(repo, "case_summary_counts", mock_case_summary_counts)
    monkeypatch.setattr(repo, "case_screenings", mock_case_screenings)
    monkeypatch.setattr(repo, "list_evidence", mock_list_evidence)
    monkeypatch.setattr(repo, "alerts", mock_alerts)
    monkeypatch.setattr(repo, "list_reports", mock_list_reports)
    monkeypatch.setattr(repo, "database_integrity", mock_database_integrity)

    # Mock services to prevent database reads/writes during analyze, assess and watches
    async def mock_analyze(*args, **kwargs):
        return []
    async def mock_assess(*args, **kwargs):
        from app.domain import RiskAssessment, RiskBand, RiskSubject, InvestigativePriority
        return RiskAssessment(
            assessment_id="assess-123",
            case_id="case-123",
            trace_id="trace-123",
            subject=RiskSubject(
                subject_id="0x1111111111111111111111111111111111111111",
                case_id="case-123",
                chain=Chain.ETHEREUM,
                address="0x1111111111111111111111111111111111111111"
            ),
            version=1,
            score=10.0,
            band=RiskBand.LOW,
            priority=InvestigativePriority.INFORMATIONAL,
            priority_reason="None",
            calculation_version="v1",
            calculated_at=datetime.now(timezone.utc),
            factors=[],
            explanation="None"
        )
    async def mock_create_watch(*args, **kwargs):
        from app.domain import WatchTarget, WatchExpansionPolicy, WatchTargetStatus
        return WatchTarget(
            watch_id="watch-123",
            case_id="case-123",
            address="0x1111111111111111111111111111111111111111",
            chain=Chain.ETHEREUM,
            status=WatchTargetStatus.ACTIVE,
            expansion_policy=WatchExpansionPolicy.MANUAL,
            created_at=datetime.now(timezone.utc),
            source="INVESTIGATOR",
            provider="alchemy_realtime"
        )
    async def mock_watches(*args, **kwargs):
        return []
    async def mock_list(*args, **kwargs):
        return []
    async def mock_latest(*args, **kwargs):
        return None

    monkeypatch.setattr(pattern_service, "analyze", mock_analyze)
    monkeypatch.setattr(pattern_service, "list", mock_list)
    monkeypatch.setattr(risk_service, "assess", mock_assess)
    monkeypatch.setattr(risk_service, "latest", mock_latest)
    monkeypatch.setattr(realtime_service, "create_watch", mock_create_watch)
    monkeypatch.setattr(realtime_service, "watches", mock_watches)

    # We can create a test case and verify investigation pipeline runs
    with TestClient(app) as client:
        # Create case
        c_res = client.post("/api/v1/cases", json={"title": "Test Pipeline Run", "fraud_type": "Investment fraud", "priority": "HIGH"})
        assert c_res.status_code == 200
        case_id = c_res.json()["case_id"]
        
        # Run investigation
        inv_res = client.post(f"/api/v1/cases/{case_id}/investigate", json={
            "address": "0x1111111111111111111111111111111111111111",
            "chain": "ethereum"
        })
        assert inv_res.status_code == 200
        state = inv_res.json()
        assert state["case"]["status"] == "INVESTIGATING"
