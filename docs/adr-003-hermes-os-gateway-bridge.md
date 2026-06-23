# ADR-003 Hermes OS Gateway Bridge

## Status
Accepted

## Context
Hermes Agent needs managed endpoints that expose Hermes OS runtime state
without making Hermes OS responsible for network serving.

## Decision
Extend `gateway/platforms/api_server.py` with Hermes OS bridge routes:
- `/v1/metrics`
- `/v1/hermes-os/runs`
- `/v1/hermes-os/ws`
