"""Bridge tests for control_center_snapshot and artifact_registry integration."""

from __future__ import annotations

import time

import pytest

from hermes_os.artifact_registry import ArtifactRegistry
from hermes_os.control_center_snapshot import ControlCenterSnapshotStore


def test_control_center_snapshot_is_latest(tmp_path: str) -> None:
    store = ControlCenterSnapshotStore()
    snap = store.capture(active_runs=3, queued_items=1, health_status="healthy")
    assert store.latest() is snap
    fetched = store.get(snap.snapshot_id)
    assert fetched is not None
    assert fetched == snap


def test_control_center_snapshot_capture_updates_metrics(tmp_path: str) -> None:
    store = ControlCenterSnapshotStore()
    snap = store.capture(active_runs=3, queued_items=1, health_status="healthy")
    assert snap.active_runs == 3
    assert snap.queued_items == 1
    assert snap.health_status == "healthy"
