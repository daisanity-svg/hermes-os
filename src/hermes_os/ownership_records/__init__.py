"""Ownership Records — pydantic-validated ownership attribution."""

from __future__ import annotations

from typing import List, Optional

from hermes_os.types import OwnershipRecord
from hermes_os.validation import OwnershipRecordModel


class OwnershipRecords:
    """Validated ownership ledger backed by pydantic models."""

    def __init__(self) -> None:
        self._records: dict[str, OwnershipRecordModel] = {}
        self._seq = 0

    def grant(
        self,
        subject_id: str,
        owner: str,
        source: str,
        provenance: Optional[dict] = None,
    ) -> OwnershipRecordModel:
        self._seq += 1
        record = OwnershipRecordModel(
            record_id=f"own_{self._seq}",
            subject_id=subject_id,
            owner=owner,
            source=source,
            provenance=provenance or {},
        )
        self._records[record.record_id] = record
        return record

    def get_for_subject(self, subject_id: str) -> List[OwnershipRecordModel]:
        return [r for r in self._records.values() if r.subject_id == subject_id]

    def current_owner(self, subject_id: str) -> Optional[str]:
        candidates = self.get_for_subject(subject_id)
        return candidates[-1].owner if candidates else None
