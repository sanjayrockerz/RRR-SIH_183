"""Run the production-like HTTP persistence workflow against BASE_URL.

Usage: python scripts/production_smoke.py https://render-service.example
The script fails closed on any non-2xx response and writes artifacts/production_smoke_report.json.
"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "production_smoke_report.json"

def call(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode())
        if response.status < 200 or response.status >= 300: raise RuntimeError(f"{method} {path}: HTTP {response.status}")
        return payload

def main():
    base = sys.argv[1] if len(sys.argv) == 2 else "http://localhost:8000"
    report = {"base_url": base, "steps": [], "status": "FAILED"}
    def step(name, method, path, body=None):
        value = call(base, method, path, body); report["steps"].append({"name":name,"status":"PASS"}); return value
    try:
        health = step("health", "GET", "/health")
        readiness = call(base, "GET", "/ready")
        report["steps"].append({"name":"ready", "status":"PASS" if readiness.get("ready") else "FAIL", "response": readiness})
        if not readiness.get("ready"): raise RuntimeError("/ready did not report READY")
        status = step("system_status", "GET", "/api/v1/system/status")
        case = step("create_case", "POST", "/api/v1/cases", {"title":"Production smoke case","fraud_type":"crypto fraud","priority":"MEDIUM"})
        case_id = case["case_id"]
        wallet = "0x" + "a" * 40
        step("add_wallet", "POST", f"/api/v1/cases/{case_id}/wallets", {"address":wallet,"chain":"ethereum"})
        trace = step("trace", "POST", f"/api/v1/cases/{case_id}/traces", {"address":wallet,"chain":"ethereum","direction":"forward","max_hops":2,"max_nodes":50,"max_edges":100,"max_transactions":100})
        risk = step("risk", "POST", f"/api/v1/cases/{case_id}/risk/assess", {"trace_id":trace["trace_id"]})
        ml = step("ml", "POST", f"/api/v1/cases/{case_id}/ml-risk/assess", {"address":wallet,"chain":"ethereum"})
        hybrid = step("hybrid", "POST", f"/api/v1/cases/{case_id}/intelligence/refresh")
        report_obj = step("report", "POST", f"/api/v1/cases/{case_id}/reports", {"report_type":"INVESTIGATION_SUMMARY","trace_id":trace["trace_id"],"created_by":"production-smoke"})
        reloaded = step("reload_case", "GET", f"/api/v1/cases/{case_id}")
        report.update({"status":"PASSED", "case_id":case_id, "trace_id":trace.get("trace_id"), "risk_assessment_id":risk.get("assessment_id"), "ml_assessment_id":ml.get("inference_id"), "hybrid_snapshot_id":hybrid.get("snapshot_id"), "report_id":report_obj.get("report_id"), "database_status":status.get("components",{}).get("database"), "migration_status":status.get("migration_state"), "model_integrity":status.get("components",{}).get("ml_model"), "persisted_case_id":reloaded.get("case_id")})
    except Exception as exc:
        report["error"] = str(exc)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASSED" else 1)

if __name__ == "__main__": main()
