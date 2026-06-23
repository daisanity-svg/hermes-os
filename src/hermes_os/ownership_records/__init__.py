"""Ownership Records — ownership attribution and provenance."""

from __future__ import annotations

from typing import List, Optional

from hermes_os.types import OwnershipRecord


class OwnershipRecords:
    def __init__(self) -> None:
        self._records: dict[str, OwnershipRecord] = {}

    def grant(
        self,
        subject_id: str,
        owner: str,
        source: str = "manual",
        metadata: Optional[dict] = None,
    ) -> OwnershipRecord:
        record = OwnershipRecord(
            record_id=f"own::{subject_id}::{owner}",
            subject_id=subject_id,
            owner=owner,
            source=source,
            metadata=metadata or {},
        )
        self._records[subject_id] = record
        return record

    def current_owner(self, subject_id: str) -> Optional[str]:
        record = self._records.get(subject_id)
        return None if record is None else record.owner

    def get_for_subject(self, subject_id: str) -> List[OwnershipRecord]:
        record = self._records.get(subject_id)
        return [] if record is None else [record]
