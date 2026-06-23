"""Control Center Bridge — connects Hermes OS to the real API Server runtime state."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from hermes_os.control_center_snapshot import ControlCenterSnapshotStore
from hermes_os.types import ControlCenterSnapshot


class RuntimeStatusAdapter:
    """Adapter over the API Server-like status mapping."""

    def __init__(self, run_statuses: Optional[Mapping[str, Dict[str, Any]]] = None) -> None:
        self._run_statuses: Dict[str, Dict[str, Any]] = dict(run_statuses or {})

    def update(self, run_statuses: Mapping[str, Dict[str, Any]]) -> None:
        self._run_statuses = dict(run_statuses)

    def count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for status in self._run_statuses.values():
            key = status.get("status", "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts

    def active_runs(self) -> int:
        return sum(
            1 for s in self._run_statuses.values() if s.get("status") == "running"
        )

    def failed_runs(self) -> int:
        return sum(
            1 for s in self._run_statuses.values() if s.get("status") == "failed"
        )


class ControlCenterBridge:
    """Produce snapshots from the real runtime state."""

    def __init__(self, snapshot_store: Optional[ControlCenterSnapshotStore] = None) -> None:
        self.snapshot_store = snapshot_store or ControlCenterSnapshotStore()
        self.runtime_adapter = RuntimeStatusAdapter()

    def attach(self, run_statuses: Mapping[str, Dict[str, Any]]) -> None:
        self.runtime_adapter.update(run_statuses)

    def capture(self, source: str = "api_server_adapter") -> ControlCenterSnapshot:
        by_status = self.runtime_adapter.count_by_status()
        snapshot = self.snapshot_store.capture(
            active_runs=self.runtime_adapter.active_runs(),
            queued_items=by_status.get("queued", 0),
            failed_items=self.runtime_adapter.failed_runs(),
            health_status="ok" if self.runtime_adapter.failed_runs() == 0 else "degraded",
            metrics={"status_breakdown": by_status, "source": source},
        )
        return snapshot
