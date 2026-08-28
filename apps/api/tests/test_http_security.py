from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.main import app


def test_health_propagates_request_id():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "incident-42"})
    assert response.headers["X-Request-ID"] == "incident-42"


def test_invalid_request_id_is_replaced():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "bad id"})
    value = response.headers["X-Request-ID"]
    assert value and value != "bad id" and len(value) == 36


def test_not_found_uses_compatible_error_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/chains/not-a-chain", headers={"X-Request-ID": "lookup-7"})
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]
    assert body["error"] == {"code": "HTTP_404", "message": body["detail"], "request_id": "lookup-7"}
