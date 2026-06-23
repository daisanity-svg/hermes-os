"""Run params records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RunParamsRecord:
    run_id: str
    params: Dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())


class RunParamsRecords:
    def __init__(self) -> None:
        self._records: Dict[str, RunParamsRecord] = {}

    def set(self, run_id: str, params: Dict[str, object]) -> RunParamsRecord:
        existing = self._records.get(run_id)
        if existing is None:
            record = RunParamsRecord(run_id=run_id, params=dict(params))
            self._records[run_id] = record
            return record
        existing.params = dict(params)
        existing.updated_at = __import__("time").time()
        return existing

    def get(self, run_id: str) -> Optional[RunParamsRecord]:
        return self._records.get(run_id)

    def list_for_run(self, run_id: str) -> Dict[str, object]:
        record = self.get(run_id)
        if record is None:
            return {"run_id": run_id, "params": {}}
        return {"run_id": run_id, "params": record.params}
