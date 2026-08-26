# Event Ingestion Boundary

`RealtimeProvider` defines subscription, unsubscribe, health, and capability contracts. `AlchemyRealtimeAdapter` is the first adapter. Raw provider JSON is validated, normalized into `RealtimeEvent`, retained as a raw reference, and passed through PostgreSQL idempotency before analysis.

Webhook authentication uses HMAC-SHA256 over the exact request body. Payload size is bounded by `REALTIME_MAX_PAYLOAD_BYTES`.
