"""Full local investigation acceptance flow.

Run against the Docker development stack with:
  $env:RUN_OPERATIONAL_ACCEPTANCE='1'
  .venv\\Scripts\\python.exe -m pytest apps/api/tests/test_operational_acceptance.py -q
"""

import os

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_OPERATIONAL_ACCEPTANCE"),
    reason="Set RUN_OPERATIONAL_ACCEPTANCE=1 against the running Docker stack",
)

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
ROOT = "0x1111111111111111111111111111111111111111"


def test_complete_persisted_investigation_flow():
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        created = client.post(
            "/api/v1/cases",
            json={"title": "Operational acceptance case", "fraud_type": "Investment fraud", "priority": "HIGH"},
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["case_id"]

        wallet = client.post(f"/api/v1/cases/{case_id}/wallets", json={"address": ROOT, "chain": "ethereum"})
        assert wallet.status_code == 200, wallet.text

        investigation = client.post(
            f"/api/v1/cases/{case_id}/investigate",
            json={"address": ROOT, "chain": "ethereum", "start_watch": True, "create_report": False},
        )
        assert investigation.status_code == 200, investigation.text

        graph = client.get(f"/api/v1/cases/{case_id}/graph")
        summary = client.get(f"/api/v1/cases/{case_id}/summary")
        ledger = client.get(f"/api/v1/cases/{case_id}/transactions")
        patterns = client.get(f"/api/v1/cases/{case_id}/patterns")
        risk = client.get(f"/api/v1/cases/{case_id}/risk")
        watches = client.get(f"/api/v1/cases/{case_id}/watches")
        for response in (graph, summary, ledger, patterns, risk, watches):
            assert response.status_code == 200, response.text

        before = summary.json()
        assert before["graph_nodes"] > 0
        assert before["graph_edges"] > 0
        assert before["transactions"] > 0
        assert before["evidence"] > 0
        assert risk.json() is not None
        assert watches.json()
        ledger_rows = ledger.json()
        assert ledger_rows
        assert any(row["risk_score"] > 0 for row in ledger_rows)
        assert any(row["risk_factors"] for row in ledger_rows)
        assert any(row["pattern_observations"] for row in ledger_rows)

        step = client.post(
            "/api/v1/dev/realtime/step",
            json={"case_id": case_id, "scenario": "ESCALATION", "scenario_seed": "acceptance", "maximum_events": 1},
        )
        assert step.status_code == 200, step.text

        after = client.get(f"/api/v1/cases/{case_id}/summary")
        evidence = client.get(f"/api/v1/cases/{case_id}/evidence")
        timeline = client.get(f"/api/v1/cases/{case_id}/timeline")
        report = client.post(f"/api/v1/cases/{case_id}/reports", json={"trace_id": investigation.json()["case"]["latest_trace"]["trace_id"]})
        integrity = client.get("/api/v1/system/integrity")
        for response in (after, evidence, timeline, report, integrity):
            assert response.status_code == 200, response.text

        assert after.json()["realtime_events"] >= before["realtime_events"]
        assert len(evidence.json()) > 0
        assert len(timeline.json()) > 0
        assert report.json()["content_hash"]
        assert integrity.json()["status"] == "PASS"
