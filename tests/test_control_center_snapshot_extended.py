"""Control Center snapshot history and diff tests."""

from __future__ import annotations

from hermes_os.control_center_snapshot import ControlCenterSnapshotStore, RuntimeStateAdapter


def test_history_returns_all_captures() -> None:
    store = ControlCenterSnapshotStore()
    store.capture(active_runs=1, queued_items=2)
    store.capture(active_runs=3, queued_items=4)
    assert len(store.history()) == 2


def test_history_supports_limit() -> None:
    store = ControlCenterSnapshotStore()
    store.capture(active_runs=1)
    store.capture(active_runs=2)
    store.capture(active_runs=3)
    last_two = store.history(limit=2)
    assert len(last_two) == 2
    assert last_two[-1].active_runs == 3


def test_diff_since_existing_snapshot() -> None:
    store = ControlCenterSnapshotStore()
    first = store.capture(active_runs=1, queued_items=1, failed_items=0)
    store.capture(active_runs=3, queued_items=2, failed_items=1)
    diff = store.diff_since(first.snapshot_id)
    assert diff is not None
    assert diff.delta["active_runs"] == 2
    assert diff.delta["queued_items"] == 1
    assert diff.delta["failed_items"] == 1


def test_diff_since_missing_snapshot_returns_none() -> None:
    store = ControlCenterSnapshotStore()
    store.capture(active_runs=1)
    assert store.diff_since("missing") is None


def test_runtime_adapter_normalizes_inputs() -> None:
    snap = RuntimeStateAdapter.to_snapshot({"active_runs": "2", "queued_items": 1})
    assert snap.active_runs == 2
    assert snap.snapshot_id == "runtime::latest"
