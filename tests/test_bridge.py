"""Bridge tests for control_center_snapshot and artifact_registry integration."""

from __future__ import annotations

import time

import pytest

from hermes_os.artifact_registry import ArtifactRegistry
from hermes_os.control_center_snapshot.bridge import ControlCenterBridge


@pytest.fixture()
def bridge() -> ControlCenterBridge:
    return ControlCenterBridge()


def test_attach_statuses_and_capture_snapshot(bridge: ControlCenterBridge) -> None:
    run_statuses = {
        "run_1": {"status": "running"},
        "run_2": {"status": "completed"},
        "run_3": {"status": "failed"},
    }
    bridge.attach(run_statuses)
    snap = bridge.capture(source="test")
    assert snap.active_runs == 1
    assert snap.queued_items == 0
    assert snap.failed_items == 1
    assert snap.health_status == "degraded"
    assert snap.metrics["status_breakdown"]["running"] == 1
    assert snap.metrics["status_breakdown"]["completed"] == 1
    assert snap.metrics["status_breakdown"]["failed"] == 1


def test_snapshot_is_persisted(bridge: ControlCenterBridge) -> None:
    bridge.attach({"run_1": {"status": "queued"}})
    snap = bridge.capture(source="test")
    fetched = bridge.snapshot_store.get(snap.snapshot_id)
    assert fetched is snap
    assert bridge.snapshot_store.latest() is snap
