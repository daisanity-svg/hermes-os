"""Action Records — append-only log of operational actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from hermes_os.types import ActionRecord, ActionStatus


class ActionRecords:
    def __init__(self) -> None:
        self._records: Dict[str, ActionRecord] = {}

    def create(
        self,
        action_id: str,
        action_type: str,
        run_id: Optional[str] = None,
        status: ActionStatus = ActionStatus.PENDING,
        input_snapshot: Optional[Dict[str, Any]] = None,
    ) -> ActionRecord:
        if action_id in self._records:
            raise ValueError(f"duplicate action id: {action_id}")
        record = ActionRecord(
            action_id=action_id,
            run_id=run_id,
            action_type=action_type,
            status=status,
            started_at=datetime.utcnow(),
            input_snapshot=input_snapshot or {},
        )
        self._records[action_id] = record
        return record

    def start(self, action_id: str) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        updated = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.RUNNING,
            started_at=record.started_at or datetime.utcnow(),
            input_snapshot=record.input_snapshot,
            output_snapshot=record.output_snapshot,
            error=record.error,
        )
        self._records[action_id] = updated
        return updated

    def complete(
        self,
        action_id: str,
        output_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        updated = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.COMPLETED,
            started_at=record.started_at,
            finished_at=datetime.utcnow(),
            input_snapshot=record.input_snapshot,
            output_snapshot=output_snapshot,
            error=record.error,
        )
        self._records[action_id] = updated
        return updated

    def fail(self, action_id: str, error: Optional[str] = None) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        updated = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.FAILED,
            started_at=record.started_at,
            finished_at=datetime.utcnow(),
            input_snapshot=record.input_snapshot,
            output_snapshot=record.output_snapshot,
            error=error,
        )
        self._records[action_id] = updated
        return updated

    def get(self, action_id: str) -> Optional[ActionRecord]:
        return self._records.get(action_id)

    def history(self, limit: Optional[int] = None) -> list[ActionRecord]:
        items = list(self._records.values())
        if limit is not None:
            return items[-limit:]
        return items
