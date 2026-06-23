"""Lifecycle Records — state transition tracking for runs and entities."""

from __future__ import annotations

from typing import Dict, List, Optional

from hermes_os.types import LifecycleEvent, RunStatus


class LifecycleRecords:
    def __init__(self) -> None:
        self._history: Dict[str, List[LifecycleEvent]] = {}
        self._status_index: Dict[str, LifecycleEvent] = {}

    def record_transition(
        self,
        subject_id: str,
        to_status: str,
        from_status: Optional[str] = None,
        actor: str = "system",
        metadata: Optional[dict] = None,
    ) -> LifecycleEvent:
        if from_status is None:
            current = self._status_index.get(subject_id)
            from_status = current.to_status if current else None
        event = LifecycleEvent(
            event_id=f"evt::{subject_id}::{to_status}",
            subject_id=subject_id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            metadata=metadata or {},
        )
        self._history.setdefault(subject_id, []).append(event)
        self._status_index[subject_id] = event
        return event

    def history_for(self, subject_id: str) -> List[LifecycleEvent]:
        return list(self._history.get(subject_id, []))

    def current_status(self, subject_id: str) -> Optional[str]:
        event = self._status_index.get(subject_id)
        return None if event is None else event.to_status
