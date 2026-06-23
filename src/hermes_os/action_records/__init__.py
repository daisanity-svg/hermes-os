"""Action Records — operational action audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from hermes_os.types import ActionRecord, ActionStatus


class ActionRecords:
    """MVP skeleton: in-memory action ledger."""

    def __init__(self) -> None:
        self._records: dict[str, ActionRecord] = {}

    def create(
        self,
        action_id: str,
        action_type: str,
        run_id: Optional[str] = None,
        input_snapshot: Optional[Dict[str, object]] = None,
    ) -> ActionRecord:
        record = ActionRecord(
            action_id=action_id,
            run_id=run_id,
            action_type=action_type,
            input_snapshot=input_snapshot or {},
        )
        self._records[record.action_id] = record
        return record

    def start(self, action_id: str) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        self._records[action_id] = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.RUNNING,
            started_at=datetime.utcnow(),
            input_snapshot=record.input_snapshot,
        )
        return self._records[action_id]

    def complete(
        self,
        action_id: str,
        output_snapshot: Optional[Dict[str, object]] = None,
    ) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        self._records[action_id] = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.COMPLETED,
            started_at=record.started_at,
            finished_at=datetime.utcnow(),
            input_snapshot=record.input_snapshot,
            output_snapshot=output_snapshot,
        )
        return self._records[action_id]

    def fail(self, action_id: str, error: str) -> Optional[ActionRecord]:
        record = self._records.get(action_id)
        if record is None:
            return None
        self._records[action_id] = ActionRecord(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            status=ActionStatus.FAILED,
            started_at=record.started_at,
            finished_at=datetime.utcnow(),
            input_snapshot=record.input_snapshot,
            error=error,
        )
        return self._records[action_id]

    def get(self, action_id: str) -> Optional[ActionRecord]:
        return self._records.get(action_id)

    def list_for_run(self, run_id: str) -> List[ActionRecord]:
        return [r for r in self._records.values() if r.run_id == run_id]
