"""Lifecycle Records — validated lifecycle state transitions."""

from __future__ import annotations

from typing import List, Optional

from hermes_os.types import LifecycleEvent
from hermes_os.validation import LifecycleEventModel


class LifecycleRecords:
    """Validated lifecycle event log."""

    def __init__(self) -> None:
        self._events: dict[str, LifecycleEventModel] = {}
        self._seq = 0

    def record_transition(
        self,
        subject_id: str,
        to_status: str,
        from_status: Optional[str] = None,
        actor: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> LifecycleEventModel:
        self._seq += 1
        event = LifecycleEventModel(
            event_id=f"evt_{self._seq}",
            subject_id=subject_id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            metadata=metadata or {},
        )
        self._events[event.event_id] = event
        return event

    def history_for(self, subject_id: str) -> List[LifecycleEventModel]:
        return [e for e in self._events.values() if e.subject_id == subject_id]

    def current_status(self, subject_id: str) -> Optional[str]:
        events = self.history_for(subject_id)
        return events[-1].to_status if events else None
