from dataclasses import dataclass
from typing import Any

import jwt


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    claims: dict[str, Any]


class JwtAuthenticator:
    """Verifies externally-issued JWTs; it never creates or infers identities."""

    def __init__(self, public_key: str | None, issuer: str | None = None, audience: str | None = None):
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience

    @property
    def configured(self) -> bool:
        return bool(self.public_key)

    def authenticate(self, token: str) -> Principal:
        if not self.configured:
            raise AuthenticationError("Authentication verifier is not configured")
        try:
            options = {"require": ["sub"]}
            claims = jwt.decode(token, self.public_key, algorithms=["RS256", "ES256"], issuer=self.issuer, audience=self.audience, options=options)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Bearer token is invalid or expired") from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("Bearer token has no valid subject")
        return Principal(subject=subject, claims=dict(claims))


def auth_status(required: bool, authenticator: JwtAuthenticator) -> dict[str, object]:
    if not required:
        return {"status": "DISABLED", "configured": authenticator.configured, "mode": "DEVELOPMENT", "detail": "API authentication is disabled for local development; do not use this mode for sensitive deployment."}
    if not authenticator.configured:
        return {"status": "NOT_CONFIGURED", "configured": False, "mode": "REQUIRED", "detail": "A trusted OIDC/JWT verification key is required before protected API access can be enabled."}
    return {"status": "READY", "configured": True, "mode": "REQUIRED", "detail": "Protected API authentication verifies externally-issued RS256/ES256 bearer tokens."}
