"""Metrics bridge tests."""

from __future__ import annotations

from hermes_os.control_center_snapshot import ControlCenterSnapshotStore
from hermes_os.metrics_bridge import MetricsBridge


def test_to_openmetrics_returns_prometheus_text() -> None:
    store = ControlCenterSnapshotStore()
    store.capture(active_runs=1, queued_items=2, health_status="healthy")
    text = MetricsBridge(store).to_openmetrics()
    assert "hermes_os_active_runs 1" in text
    assert "hermes_os_queued_items 2" in text


def test_to_json_returns_status_block() -> None:
    store = ControlCenterSnapshotStore()
    store.capture(active_runs=0, queued_items=0, health_status="healthy")
    payload = MetricsBridge(store).to_json()
    assert payload["status"] == "ok"
    assert payload["schema_version"] == "cos-runtime/status/v1"
    assert payload["snapshot"]["active_runs"] == 0


def test_to_json_when_empty_returns_unavailable() -> None:
    payload = MetricsBridge().to_json()
    assert payload == {"schema_version": "cos-runtime/status/v1", "status": "unavailable"}
