# Security controls

Implemented boundaries include input validation, backend-only secrets, Alchemy HMAC verification, replay/idempotency checks, request IDs, structured error envelopes, bounded provider requests, evidence hashes, append-only custody events and opt-in JWT verification.

Required before sensitive deployment: OIDC/JWKS lifecycle, case-level RBAC, export authorization, rate limiting, secret manager integration, dependency scanning, TLS/reverse proxy, monitoring and incident response controls.
