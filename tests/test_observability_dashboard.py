"""Observability dashboard snapshot tests."""

from __future__ import annotations

from hermes_os.observability import ObservabilityLog


def test_dashboard_snapshot_includes_required_keys() -> None:
    log = ObservabilityLog()
    log.log("heartbeat", active_runs=1)
    log.log("heartbeat", active_runs=0)
    snapshot = log.dashboard_snapshot()
    assert snapshot["status"] == "ok"
    assert snapshot["sample_count"] == 2
    assert snapshot["updated_at"] > 0
