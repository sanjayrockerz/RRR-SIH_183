# ADR 0001: Start as a modular monolith

## Decision

Keep provider, trace, evidence, and case boundaries as Python modules inside one FastAPI deployable until independent scaling or ownership is demonstrated.

## Rationale

The first vertical slice needs strong domain boundaries without the operational cost and false separation of empty microservices.
