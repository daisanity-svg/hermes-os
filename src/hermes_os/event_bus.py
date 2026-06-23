"""In-process event bus for Hermes OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class DomainEvent:
    name: str
    source: str
    occurred_at: datetime
    payload: Dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[DomainEvent], None]]] = {}
        self._history: List[DomainEvent] = []

    def subscribe(self, event_name: str, handler: Callable[[DomainEvent], None]) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        self._history.append(event)
        for handler in list(self._handlers.get(event.name, [])):
            handler(event)

    def replay(self, handler: Callable[[DomainEvent], None], *, limit: Optional[int] = None) -> None:
        history = self._history
        if limit is not None:
            history = history[-limit:]
        for event in history:
            handler(event)
