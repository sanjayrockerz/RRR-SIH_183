# ADR 0007: Webhook-first real-time retracing boundary

## Decision

Use a provider-independent `RealtimeProvider` and canonical `RealtimeEvent` boundary. Implement Alchemy Notify Address Activity as the first adapter, authenticated by HMAC, with PostgreSQL event idempotency and case-scoped watch targets.

## Rationale

Polling an historical endpoint every few seconds would not be real-time ingestion. Webhooks provide a clear capability boundary while keeping the domain independent of Alchemy.

## Consequences

Live status requires externally provisioned Alchemy webhook configuration. Events remain `OBSERVED` until confirmation reconciliation is implemented. Simulated events are explicitly labeled.
