# Authentication boundary

RRR now has an opt-in bearer-token verification boundary. Set `AUTH_REQUIRED=true` and provide a PEM-encoded trusted OIDC/JWT verification key in `AUTH_JWT_PUBLIC_KEY`; the API then verifies externally-issued RS256 or ES256 tokens and requires a non-empty `sub` claim on protected `/api/v1` routes. No identity is inferred from UI initials, request fields, or wallet labels.

Health, OpenAPI, and the HMAC-authenticated realtime webhook remain separately reachable for operational/protocol reasons. `GET /api/v1/auth/status` exposes `DISABLED`, `NOT_CONFIGURED`, or `READY` without exposing key material.

This is an authentication boundary, not complete authorization. Case-level access policy, issuer/JWKS discovery, role mapping, tenant isolation, token revocation, audit actor binding, and secure deployment/TLS controls remain required before sensitive LEA deployment. Local development defaults to `AUTH_REQUIRED=false` and must not be used for production.
