import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.config import settings
from app.memory_repository import MemoryCaseRepository


@pytest.fixture
def development_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "blockchain_data_mode", "DEVELOPMENT_FIXTURE")
    monkeypatch.setattr(settings, "database_url", "postgresql://postgres:postgres@127.0.0.1:65439/rrr_test_unavailable")
    memory_repo = MemoryCaseRepository()
    main_module.repo = memory_repo
    for service in (
        main_module.pattern_service, main_module.risk_service,
        main_module.alert_service, main_module.evidence_service,
        main_module.report_service, main_module.cross_chain_service,
        main_module.realtime_service, main_module.synthetic_engine,
        main_module.case_fusion_service, main_module.investigation_orchestrator,
        main_module.threat_intel_service, main_module.recommendation_service,
        main_module.ml_inference_service, main_module.vasp_action_package_service,
        main_module.hybrid_intelligence_service,
    ):
        if hasattr(service, "repository"):
            service.repository = memory_repo
    with TestClient(app) as client:
        yield client


def test_realtime_demo_transitions_p2_to_p1(development_client):
    seeded = development_client.post("/api/v1/development/realtime/demo/reset")
    assert seeded.status_code == 200
    before = seeded.json()
    assert before["fixture"] == "RRR-DEMO-REALTIME-001"
    assert before["data_origin"] == "DEVELOPMENT_FIXTURE"
    assert before["before"]["priority"] == "P2"
    assert before["watch"]["status"] == "ACTIVE"

    replay = development_client.post(
        "/api/v1/development/realtime/demo/replay",
        json={"case_id": before["case_id"]},
    )
    assert replay.status_code == 200
    result = replay.json()
    assert result["after"]["priority"] == "P1"
    assert result["priority_changed"] is True
    assert result["previous_priority"] == "P2"
    assert "REALTIME_MOVEMENT" in result["after"]["reason_codes"]
    assert result["results"][0]["duplicate"] is False
    assert result["results"][0]["evidence_id"]
    assert result["alert"]
    assert result["after"]["realtime_state"]["new_movement_detected"] is True
    assert "PATTERN_ANALYZED" in result["pipeline_events_after_event"]
    assert result["after"]["deterministic_risk"]
    assert result["after"]["ml_behavioural_intelligence"]
    assert result["duplicate_replay"][0]["duplicate"] is True
    assert result["duplicate_replay"][0]["transaction_id"] is None
    assert result["counts_after_event"]["transactions"] == result["counts_after_duplicate"]["transactions"]
    assert result["counts_after_event"]["alerts"] == result["counts_after_duplicate"]["alerts"]
    assert result["counts_after_event"]["hybrid_snapshots"] == result["counts_after_duplicate"]["hybrid_snapshots"]


def test_realtime_demo_never_claims_live_provider(development_client):
    readiness = development_client.get("/api/v1/system/demo-readiness")
    assert readiness.status_code == 200
    assert readiness.json()["data_origin"] == "DEVELOPMENT_FIXTURE"
    assert readiness.json()["fixture"] == "RRR-DEMO-REALTIME-001"

    seeded = development_client.post("/api/v1/development/realtime/demo/reset").json()
    replay = development_client.post(
        "/api/v1/development/realtime/demo/replay",
        json={"case_id": seeded["case_id"]},
    ).json()
    assert replay["trigger"]["provider"] == "DEVELOPMENT SYNTHETIC"
    assert replay["trigger"]["raw_provider_reference"]["data_origin"] == "DEVELOPMENT_FIXTURE"
