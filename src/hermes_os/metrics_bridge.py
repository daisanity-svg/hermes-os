"""Hermes OS Metrics Bridge — format ControlCenterSnapshot for Hermes Agent."""

from __future__ import annotations

from typing import Any, Dict

from hermes_os.control_center_snapshot import ControlCenterSnapshotStore


class MetricsBridge:
    def __init__(self, store: ControlCenterSnapshotStore | None = None) -> None:
        self.store = store or ControlCenterSnapshotStore()

    def to_openmetrics(self) -> str:
        snap = self.store.latest()
        if snap is None:
            return ""
        lines = [
            f"# HELP hermes_os_active_runs Active runs",
            f"# TYPE hermes_os_active_runs gauge",
            f"hermes_os_active_runs {snap.active_runs}",
            f"# HELP hermes_os_queued_items Queued workload items",
            f"# TYPE hermes_os_queued_items gauge",
            f"hermes_os_queued_items {snap.queued_items}",
        ]
        return "\n".join(lines) + "\n"

    def to_json(self) -> Dict[str, Any]:
        snap = self.store.latest()
        if snap is None:
            return {
                "schema_version": "cos-runtime/status/v1",
                "status": "unavailable",
            }
        return {
            "schema_version": "cos-runtime/status/v1",
            "status": "ok",
            "snapshot": {
                "snapshot_id": snap.snapshot_id,
                "captured_at": snap.captured_at.isoformat() if hasattr(snap.captured_at, "isoformat") else str(snap.captured_at),
                "active_runs": snap.active_runs,
                "queued_items": snap.queued_items,
                "failed_items": snap.failed_items,
                "health_status": snap.health_status,
                "metrics": snap.metrics,
            },
        }
