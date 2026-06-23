"""Control Center Snapshot — system state snapshots for dashboards."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from hermes_os.types import ControlCenterSnapshot


class ControlCenterSnapshotStore:
    """MVP skeleton: in-memory snapshot persistence."""

    def __init__(self) -> None:
        self._snapshots: dict[str, ControlCenterSnapshot] = {}

    def capture(
        self,
        active_runs: int = 0,
        queued_items: int = 0,
        failed_items: int = 0,
        health_status: str = "unknown",
        metrics: Optional[Dict[str, object]] = None,
    ) -> ControlCenterSnapshot:
        snapshot = ControlCenterSnapshot(
            snapshot_id=f"snap_{len(self._snapshots) + 1}",
            captured_at=datetime.utcnow(),
            active_runs=active_runs,
            queued_items=queued_items,
            failed_items=failed_items,
            health_status=health_status,
            metrics=metrics or {},
        )
        self._snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def get(self, snapshot_id: str) -> Optional[ControlCenterSnapshot]:
        return self._snapshots.get(snapshot_id)

    def latest(self) -> Optional[ControlCenterSnapshot]:
        if not self._snapshots:
            return None
        return max(self._snapshots.values(), key=lambda s: s.captured_at)
