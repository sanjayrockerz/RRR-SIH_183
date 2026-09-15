"""Execute the deterministic DEVELOPMENT_FIXTURE realtime closure demo."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app
from app.config import settings
from app.memory_repository import MemoryCaseRepository

def main():
    settings.app_env = "development"
    settings.blockchain_data_mode = "DEVELOPMENT_FIXTURE"
    settings.database_url = "postgresql://postgres:postgres@127.0.0.1:65439/rrr_demo_unavailable"
    memory_repo = MemoryCaseRepository()
    main_module.repo = memory_repo
    services = (main_module.pattern_service, main_module.risk_service, main_module.alert_service,
                main_module.evidence_service, main_module.report_service, main_module.cross_chain_service,
                main_module.realtime_service, main_module.synthetic_engine, main_module.case_fusion_service,
                main_module.investigation_orchestrator, main_module.threat_intel_service,
                main_module.recommendation_service, main_module.ml_inference_service,
                main_module.vasp_action_package_service, main_module.hybrid_intelligence_service)
    for service in services:
        if hasattr(service, "repository"):
            service.repository = memory_repo
    with TestClient(app) as client:
        seeded = client.post("/api/v1/development/realtime/demo/reset").json()
        result = client.post("/api/v1/development/realtime/demo/replay", json={"case_id": seeded["case_id"]}).json()
    output = {
        "fixture": result["fixture"], "data_origin": result["data_origin"],
        "case_id": result["case_id"], "initial_hybrid": result["before"]["priority"],
        "final_hybrid": result["after"]["priority"], "alert_id": result["alert"]["alert_id"],
        "event_id": result["trigger"]["event_id"], "transaction_id": result["results"][0]["transaction_id"],
        "graph_edge_id": result["results"][0]["graph_edge_id"], "evidence_id": result["results"][0]["evidence_id"],
        "first_replay_duplicate": result["results"][0]["duplicate"],
        "second_replay_duplicate": result["duplicate_replay"][0]["duplicate"],
        "counts_after_event": result["counts_after_event"],
        "counts_after_duplicate": result["counts_after_duplicate"],
        "p2_to_p1": result["before"]["priority"] == "P2" and result["after"]["priority"] == "P1",
        "idempotent": result["counts_after_event"] == result["counts_after_duplicate"],
    }
    out_path = ROOT / "artifacts" / "phase1_phase3_realtime_demo.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    if not (output["p2_to_p1"] and output["idempotent"]):
        raise SystemExit(1)

if __name__ == "__main__": main()
