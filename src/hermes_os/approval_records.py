"""Approval records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ApprovalRecord:
    item_id: str
    status: str
    created_at: float
    updated_at: float
    metadata: dict = field(default_factory=dict)


class ApprovalRecords:
    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRecord] = {}

    def start(self, item_id: str, metadata: Optional[dict] = None) -> ApprovalRecord:
        now = __import__("time").time()
        record = ApprovalRecord(
            item_id=item_id,
            status="pending",
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._records[item_id] = record
        return record

    def approve(self, item_id: str) -> Optional[ApprovalRecord]:
        record = self._records.get(item_id)
        if record is None:
            return None
        record.status = "approved"
        record.updated_at = __import__("time").time()
        return record

    def reject(self, item_id: str) -> Optional[ApprovalRecord]:
        record = self._records.get(item_id)
        if record is None:
            return None
        record.status = "rejected"
        record.updated_at = __import__("time").time()
        return record

    def get(self, item_id: str) -> Optional[ApprovalRecord]:
        return self._records.get(item_id)

    def list_pending(self) -> List[ApprovalRecord]:
        return [record for record in self._records.values() if record.status == "pending"]
