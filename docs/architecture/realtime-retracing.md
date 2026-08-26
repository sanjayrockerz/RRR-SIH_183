# RRR Real-Time Retracing

Phase 7 adds a provider-independent event boundary for incremental investigation updates.

## Capability truth

The current live adapter is Alchemy Notify Address Activity via webhook. It is `SUPPORTED` only when `ALCHEMY_API_KEY`, `ALCHEMY_WEBHOOK_ID`, and `ALCHEMY_WEBHOOK_SIGNING_KEY` are configured. WebSocket ingestion and automatic webhook registration are not configured. Missing configuration is exposed as `NOT_CONFIGURED`; it is never presented as live. The simulated event endpoint is an explicit test seam and returns `SIMULATED`.

## Event flow

`provider webhook -> raw signature validation -> canonical RealtimeEvent -> idempotent event store -> watch matching -> transaction/transfer/evidence persistence -> graph edge -> pattern analysis -> rule-based risk reassessment -> timeline/change set/alert candidate`.

The provider payload is retained in `raw_provider_reference`. The canonical event ID is deterministic over chain, transaction, transfer index, event type, addresses, and asset. Replays therefore do not duplicate observations.

## Reorgs and confirmations

Removed provider activities are stored as `REORGED` observations and do not create new graph edges. Normal webhook activity is initially `OBSERVED`; confirmation-depth reconciliation is a future provider capability.

## Scope

Watch targets are case-scoped and address-specific. Expansion policy and limits are stored for future controlled graph expansion; no unbounded recursive monitoring is performed. PostgreSQL is the source of truth.
