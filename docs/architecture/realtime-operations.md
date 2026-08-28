# Realtime delivery operations

The signed Alchemy Address Activity webhook remains the ingress boundary. Every normalized event is idempotently stored before case application. Processing attempts are persisted in `processing_attempts` and the event records its attempt count and next operational state.

## Delivery states

- `APPLIED`: the event completed the current application path.
- `RETRY_PENDING`: processing failed before the configured attempt limit; a provider retry or operator replay may retry it.
- `DEAD_LETTER`: the configured attempt limit was reached. It is not silently discarded and requires explicit replay after investigation.
- `REORGED`: the provider marked the observation removed; no new graph edge is created.

The event identity and provider event uniqueness constraints prevent duplicate blockchain observations and duplicate case applications. A retryable stored event is allowed back through the application path; an applied or dead-lettered event remains idempotent.

## Operations API

- `GET /api/v1/realtime/failures?limit=100` lists retry-pending and dead-letter events with their attempt history.
- `POST /api/v1/realtime/events/{event_id}/replay` explicitly resets an event’s delivery state and reprocesses it.

These operational endpoints are currently an internal boundary and must be placed behind authentication/RBAC before production deployment. No background retry worker is enabled yet; Phase G currently provides durable state and controlled replay, not a distributed queue.
