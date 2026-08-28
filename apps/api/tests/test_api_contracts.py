from app.main import app


def test_phase_b_operational_and_registry_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/system/status" in paths
    assert "/api/v1/system/providers" in paths
    assert "/api/v1/system/dependencies" in paths
    assert "/api/v1/system/database" in paths
    assert "/api/v1/dashboard/summary" in paths
    assert "/api/v1/cases" in paths
    assert "/api/v1/cases/{case_id}/evidence" in paths
    assert "/api/v1/evidence" in paths
    assert "/api/v1/evidence/{evidence_id}" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/providers" in paths
    assert "/api/v1/entities/{entity_id}/attributions" in paths
    assert "/api/v1/attribution-sources" in paths
    assert "/api/v1/addresses/{chain}/{address}/sanctions" in paths
    assert "/api/v1/cases/{case_id}/cyber/screen" in paths
    assert "/api/v1/cases/{case_id}/cyber/screening" in paths
    assert "/api/v1/intelligence/sources" in paths
    assert "/api/v1/intelligence/indicators" in paths
    assert "/api/v1/contracts/{chain}/{address}/security" in paths
    assert "/api/v1/realtime/failures" in paths
    assert "/api/v1/realtime/events/{event_id}/replay" in paths
    assert "/api/v1/cases/{case_id}/alerts/{alert_id}/review" in paths
    assert "/api/v1/cases/{case_id}/alerts/{alert_id}/reviews" in paths
    assert "/api/v1/cases/{case_id}/evidence/manifest" in paths
    assert "/api/v1/cases/{case_id}/evidence/ledger" in paths
    assert "/api/v1/cases/{case_id}/evidence/{evidence_id}/chain-of-custody" in paths
    assert "/api/v1/cases/{case_id}/reports" in paths
    assert "/api/v1/cases/{case_id}/reports/{report_id}" in paths
    assert "/api/v1/cases/{case_id}/audit-events" in paths
    assert "/api/v1/cases/{case_id}/related" in paths
    assert "/api/v1/wallets/{chain}/{address}" in paths
    assert "/api/v1/auth/status" in paths


def test_phase_b_case_lifecycle_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/cases/{case_id}/close" in paths
    assert "/api/v1/cases/{case_id}/reopen" in paths
    assert "/api/v1/cases/{case_id}/status" in paths
    assert "/api/v1/cases/{case_id}/workflow" in paths
