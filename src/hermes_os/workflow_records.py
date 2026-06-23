"""Workflow records."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WorkflowRecord:
    workflow_id: str
    root_item_id: str
    status: str
    created_at: float
    updated_at: float
    metadata: dict = field(default_factory=dict)


class WorkflowRecords:
    def __init__(self) -> None:
        self._records: Dict[str, WorkflowRecord] = {}

    def start(self, workflow_id: str, root_item_id: str, metadata: Optional[dict] = None) -> WorkflowRecord:
        now = time.time()
        record = WorkflowRecord(
            workflow_id=workflow_id,
            root_item_id=root_item_id,
            status="running",
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._records[workflow_id] = record
        return record

    def complete(self, workflow_id: str) -> Optional[WorkflowRecord]:
        record = self._records.get(workflow_id)
        if record is None:
            return None
        record.status = "completed"
        record.updated_at = time.time()
        return record

    def get(self, workflow_id: str) -> Optional[WorkflowRecord]:
        return self._records.get(workflow_id)

    def list_running(self) -> List[WorkflowRecord]:
        return [record for record in self._records.values() if record.status == "running"]
