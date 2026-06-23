"""Control Center Snapshot plus a runtime-state adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from hermes_os.types import ControlCenterSnapshot


@dataclass
class SnapshotDiff:
    before: ControlCenterSnapshot
    after: ControlCenterSnapshot

    @property
    def delta(self) -> Dict[str, int]:
        return {
            "active_runs": self.after.active_runs - self.before.active_runs,
            "queued_items": self.after.queued_items - self.before.queued_items,
            "failed_items": self.after.failed_items - self.before.failed_items,
        }


class ControlCenterSnapshotStore:
    def __init__(self) -> None:
        self._latest: Optional[ControlCenterSnapshot] = None
        self._history: Dict[str, ControlCenterSnapshot] = {}

    def capture(
        self,
        active_runs: int = 0,
        queued_items: int = 0,
        failed_items: int = 0,
        health_status: str = "unknown",
        metrics: Optional[Dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
    ) -> ControlCenterSnapshot:
        snapshot_id = snapshot_id or f"snap::{datetime.utcnow().isoformat()}::{id(self)}"
        snap = ControlCenterSnapshot(
            snapshot_id=snapshot_id,
            captured_at=datetime.utcnow(),
            active_runs=active_runs,
            queued_items=queued_items,
            failed_items=failed_items,
            health_status=health_status,
            metrics=metrics or {},
        )
        self._latest = snap
        self._history[snap.snapshot_id] = snap
        return snap

    def latest(self) -> Optional[ControlCenterSnapshot]:
        return self._latest

    def get(self, snapshot_id: str) -> Optional[ControlCenterSnapshot]:
        return self._history.get(snapshot_id)

    def history(self, limit: Optional[int] = None) -> list[ControlCenterSnapshot]:
        snapshots = list(self._history.values())
        if limit is not None:
            return snapshots[-limit:]
        return snapshots

    def diff_since(self, snapshot_id: str) -> Optional[SnapshotDiff]:
        before = self._history.get(snapshot_id)
        if before is None or self._latest is None:
            return None
        return SnapshotDiff(before=before, after=self._latest)


class RuntimeStateAdapter:
    """Hermes Agent runtime state bridge for Control Center."""

    @staticmethod
    def to_snapshot(state: Dict[str, Any]) -> ControlCenterSnapshot:
        return ControlCenterSnapshot(
            snapshot_id="runtime::latest",
            captured_at=datetime.utcnow(),
            active_runs=int(state.get("active_runs", 0)),
            queued_items=int(state.get("queued_items", 0)),
            failed_items=int(state.get("failed_items", 0)),
            health_status=str(state.get("health_status", "unknown")),
            metrics=dict(state.get("metrics") or {}),
        )
