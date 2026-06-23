# ADR-002 Event Bus Design

## Status
Accepted

## Context
Hermes OS needs a decoupled publish/subscribe path for lifecycle events
(submitted, drained, completed, failed, priority updated, retried, cancelled).

## Decision
Introduce an in-process `EventBus` in `src/hermes_os/event_bus.py` and
publish through `ProcessAdapter._publish`. Persist every event to
`OperationalMemoryLog` for replay and audit.
