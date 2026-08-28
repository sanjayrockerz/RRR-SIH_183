"""
Phase 10E Runtime Smoke Tests
Validates the full browser → FastAPI → PostgreSQL/Neo4j open-case flow.
Run with: pytest tests/test_runtime_open_case.py -v

Requires the stack to be running: docker compose up -d
"""
import os
import pytest
import httpx

BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=30)


# -- 1. Health ----------------------------------------------------------------

def test_system_status_reachable(client):
    """API must be reachable and report a valid system status."""
    r = client.get("/api/v1/system/status")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "system" in body, "system field missing from status response"


def test_system_dependencies(client):
    """Dependency health endpoint must return without server error."""
    r = client.get("/api/v1/system/dependencies")
    assert r.status_code in (200, 206), f"Unexpected status: {r.status_code}"


# -- 2. Cases list ------------------------------------------------------------

def test_list_cases(client):
    """GET /api/v1/cases must return a list (possibly empty)."""
    r = client.get("/api/v1/cases")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# -- 3. Seed case -------------------------------------------------------------

@pytest.fixture(scope="module")
def seeded_case(client):
    """Create a fully-persisted fixture investigation and return its ID."""
    r = client.post("/api/v1/dev/seed-case")
    assert r.status_code == 200, f"Seed failed {r.status_code}: {r.text}"
    body = r.json()
    assert "case_id" in body
    assert "trace_id" in body
    return body


def test_seed_case_creates_case(seeded_case):
    """Seed must return a valid case_id and trace_id."""
    assert seeded_case["case_id"]
    assert seeded_case["trace_id"]


def test_seed_case_mode(seeded_case):
    """Seed should produce development fixture data."""
    assert "FIXTURE" in seeded_case.get("mode", "").upper()


# -- 4. Case open flow --------------------------------------------------------

def test_get_case(client, seeded_case):
    """GET /api/v1/cases/{id} must return the seeded case without 500."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}")
    assert r.status_code == 200, f"get_case failed: {r.text}"
    body = r.json()
    assert body["case_id"] == case_id
    assert body["title"]


def test_case_summary(client, seeded_case):
    """GET /api/v1/cases/{id}/summary must not 500."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/summary")
    assert r.status_code == 200, f"summary 500: {r.text}"
    body = r.json()
    assert "wallets" in body
    assert "transactions" in body


def test_case_operational_state(client, seeded_case):
    """
    GET /api/v1/cases/{id}/operational-state is the critical route.
    It must return 200 with stages populated, never 500.
    This was the root cause of Phase 10E open-case failures.
    """
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/operational-state")
    assert r.status_code == 200, f"operational-state 500: {r.text}"
    body = r.json()
    assert "stages" in body
    assert len(body["stages"]) > 0, "Expected at least one operational stage"
    assert body["case"]["case_id"] == case_id


def test_case_operational_state_never_500_on_attribution(client, seeded_case):
    """
    Specifically verify that the attribution catalog (which may include
    MIXER_CONTRACT / BRIDGE_DEPOSIT / DEPOSIT_ADDRESS roles) does NOT
    cause a Pydantic ValidationError 500.
    """
    case_id = seeded_case["case_id"]
    # Call multiple times to confirm stability
    for _ in range(3):
        r = client.get(f"/api/v1/cases/{case_id}/operational-state")
        assert r.status_code == 200, f"Repeated call failed: {r.text}"


def test_case_transactions(client, seeded_case):
    """GET /api/v1/cases/{id}/transactions must return a list."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/transactions?limit=10")
    assert r.status_code == 200, f"transactions 500: {r.text}"
    rows = r.json()
    assert isinstance(rows, list)
    assert rows, "Seeded case should expose persisted ledger rows"
    first = rows[0]
    for field in ("risk_score", "risk_band", "risk_factors", "pattern_observations", "entity_exposure", "evidence_ids"):
        assert field in first, f"Ledger row missing {field}"


def test_graph_layout(client, seeded_case):
    """GET /api/v1/cases/{id}/graph/layout must not 500."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/graph/layout")
    assert r.status_code in (200, 404), f"graph/layout unexpected: {r.text}"


def test_case_risk(client, seeded_case):
    """GET /api/v1/cases/{id}/risk must return assessment data."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/risk")
    assert r.status_code == 200, f"risk 500: {r.text}"


def test_case_evidence(client, seeded_case):
    """GET /api/v1/cases/{id}/evidence must return a list."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/evidence")
    assert r.status_code == 200, f"evidence 500: {r.text}"
    assert isinstance(r.json(), list)


def test_case_timeline(client, seeded_case):
    """GET /api/v1/cases/{id}/timeline must return a list."""
    case_id = seeded_case["case_id"]
    r = client.get(f"/api/v1/cases/{case_id}/timeline")
    assert r.status_code == 200, f"timeline 500: {r.text}"
    assert isinstance(r.json(), list)


# -- 5. CORS headers ----------------------------------------------------------

def test_cors_allows_frontend_origin(client):
    """
    FastAPI must respond with CORS headers allowing http://localhost:5173.
    This validates the CORSMiddleware configuration.
    """
    r = client.options(
        "/api/v1/cases",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert r.status_code in (200, 204), f"CORS preflight failed: {r.status_code}"
    allowed_origins = r.headers.get("access-control-allow-origin", "")
    assert "localhost:5173" in allowed_origins or allowed_origins == "*", (
        f"CORS origin not allowed. Header: {allowed_origins}"
    )
