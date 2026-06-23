# ADR-004 Circuit Breaker and Retry Policy

## Status
Accepted

## Context
ProcessAdapter must fail fast under repeated downstream errors.

## Decision
Add failure counting and exponential backoff:
- `circuit_failure_threshold`
- `circuit_recovery_seconds`
- status flow includes `retry` and `circuit_open`.
