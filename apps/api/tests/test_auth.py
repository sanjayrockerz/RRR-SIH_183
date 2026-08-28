from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth import AuthenticationError, JwtAuthenticator
from app.config import settings
from app.main import app


def test_unconfigured_authenticator_is_explicit():
    verifier = JwtAuthenticator(None)
    assert not verifier.configured
    with pytest.raises(AuthenticationError, match="not configured"):
        verifier.authenticate("token")


def test_jwt_authenticator_requires_external_subject(rsa_keys):
    private_key, public_key = rsa_keys
    verifier = JwtAuthenticator(public_key)
    token = jwt.encode({"sub": "investigator-7", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, private_key, algorithm="RS256")
    principal = verifier.authenticate(token)
    assert principal.subject == "investigator-7"


def test_invalid_token_is_rejected(rsa_keys):
    _, public_key = rsa_keys
    with pytest.raises(AuthenticationError, match="invalid"):
        JwtAuthenticator(public_key).authenticate("not-a-jwt")


def test_required_mode_rejects_unauthenticated_api_access(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr("app.main.authenticator", JwtAuthenticator(None))
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get("/api/v1/cases")
        status = client.get("/api/v1/auth/status")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert status.status_code == 200
    assert status.json()["status"] == "NOT_CONFIGURED"


@pytest.fixture
def rsa_keys():
    cryptography = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
    private = cryptography.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_bytes = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private_bytes, public_bytes
