"""Hermes OS observability helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StructuredLogEntry:
    timestamp: float = field(default_factory=time.time)
    level: str = "info"
    source: str = "hermes_os"
    event: str = "noop"
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


class ObservabilityLog:
    def __init__(self) -> None:
        self._entries: List[StructuredLogEntry] = []

    def log(self, event: str, level: str = "info", **payload: Any) -> StructuredLogEntry:
        entry = StructuredLogEntry(level=level, event=event, payload=dict(payload))
        self._entries.append(entry)
        return entry

    def entries(self) -> List[StructuredLogEntry]:
        return list(self._entries)

    def dashboard_snapshot(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": "ok",
            "sample_count": len(self._entries),
            "updated_at": self._entries[-1].timestamp if self._entries else time.time(),
            "last_event": self._entries[-1].event if self._entries else None,
        }
        return payload
