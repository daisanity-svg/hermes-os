"""Hermes OS Watchdog — StatusCollector：從 run artifacts 收集目前任務狀態。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from hermes_os.watchdog.schemas import TaskState, TaskStatus


# 預設監控的 run artifacts 根目錄
DEFAULT_ARTIFACTS_ROOT = Path.home() / ".hermes" / "artifacts"


def _parse_state(payload: dict) -> Optional[TaskStatus]:
    raw = payload.get("status") or payload.get("state") or payload.get("run_status")
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    mapping = {
        "queued": TaskStatus.PENDING,
        "pending": TaskStatus.PENDING,
        "in_progress": TaskStatus.IN_PROGRESS,
        "running": TaskStatus.IN_PROGRESS,
        "completed": TaskStatus.COMPLETED,
        "succeeded": TaskStatus.COMPLETED,
        "failed": TaskStatus.FAILED,
        "error": TaskStatus.FAILED,
        "paused": TaskStatus.PAUSED,
        "escalated": TaskStatus.ESCALATED,
    }
    return mapping.get(normalized)


def _read_run_json(run_dir: Path) -> Optional[dict]:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return None
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class StatusCollector:
    """讀取 run artifacts 並轉為 List[TaskState]。

    artifacts 結構假設：
    ~/.hermes/artifacts/<run_id>/
      ├─ status.json
      └─ ...
    """

    def __init__(self, artifacts_root: Optional[Path] = None) -> None:
        self.root = artifacts_root or DEFAULT_ARTIFACTS_ROOT

    def collect(self) -> List[TaskState]:
        if not self.root.exists():
            return []
        results: List[TaskState] = []
        for run_dir in sorted(self.root.iterdir()):
            if not run_dir.is_dir():
                continue
            payload = _read_run_json(run_dir)
            if payload is None:
                continue

            status = _parse_state(payload) or TaskStatus.PENDING
            metadata = payload.get("metadata") or payload.get("meta") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            task_id = str(payload.get("run_id") or payload.get("task_id") or run_dir.name)
            now = TaskState.model_fields.get("last_activity_ts")  # pydantic v2 hint only
            # 直接用 datetime
            from datetime import datetime as _dt

            last_activity_raw = payload.get("updated_at") or payload.get(
                "last_activity_ts"
            )
            if isinstance(last_activity_raw, str):
                try:
                    last_activity_ts = _dt.fromisoformat(last_activity_raw)
                except ValueError:
                    last_activity_ts = _dt.utcnow()
            else:
                last_activity_ts = _dt.utcnow()

            last_user_reply_raw = payload.get("last_user_reply_ts")
            last_user_reply_ts: Optional[_dt] = None
            if isinstance(last_user_reply_raw, str):
                try:
                    last_user_reply_ts = _dt.fromisoformat(last_user_reply_raw)
                except ValueError:
                    pass

            results.append(
                TaskState(
                    task_id=task_id,
                    project=str(payload.get("project") or "default"),
                    status=status,
                    last_activity_ts=last_activity_ts,
                    last_user_reply_ts=last_user_reply_ts,
                    error_summary=str(payload.get("error"))
                    if payload.get("error")
                    else None,
                    blockers=list(payload.get("blockers") or []),
                    current_action=str(payload.get("current_action"))
                    if payload.get("current_action")
                    else None,
                    owner=str(payload.get("owner")) if payload.get("owner") else None,
                )
            )
        return results
