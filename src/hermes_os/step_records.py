"""Step records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StepRecord:
    step_id: str
    workflow_id: Optional[str]
    status: str
    created_at: float
    updated_at: float
    metadata: dict = field(default_factory=dict)


class StepRecords:
    def __init__(self) -> None:
        self._records: Dict[str, StepRecord] = {}

    def start(self, step_id: str, workflow_id: Optional[str], metadata: Optional[dict] = None) -> StepRecord:
        now = float(metadata.get("created_at", __import__("time").time())) if metadata else __import__("time").time()
        record = StepRecord(
            step_id=step_id,
            workflow_id=workflow_id,
            status="running",
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._records[step_id] = record
        return record

    def get(self, step_id: str) -> Optional[StepRecord]:
        return self._records.get(step_id)

    def list_for_workflow(self, workflow_id: Optional[str]) -> List[StepRecord]:
        return [
            step
            for step in self._records.values()
            if step.workflow_id == workflow_id and step.status == "running"
        ]
