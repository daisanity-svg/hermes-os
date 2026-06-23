"""Operational Memory Log — append-only log with rich query DSL."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from hermes_os.types import MemoryLogEntry


class OperationalMemoryLog:
    def __init__(self) -> None:
        self._entries: Dict[str, MemoryLogEntry] = {}

    def append(
        self,
        source: str,
        category: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        entry_id: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> MemoryLogEntry:
        eid = entry_id or f"mem-{uuid.uuid4().hex}"
        entry = MemoryLogEntry(
            entry_id=eid,
            source=source,
            category=category,
            occurred_at=occurred_at or datetime.utcnow(),
            content=content,
            metadata=metadata or {},
        )
        self._entries[eid] = entry
        return entry

    def count(self) -> int:
        return len(self._entries)

    def query(
        self,
        *,
        source: Optional[str] = None,
        category: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        contains: Optional[str] = None,
    ) -> List[MemoryLogEntry]:
        results = list(self._entries.values())
        if source is not None:
            results = [r for r in results if r.source == source]
        if category is not None:
            results = [r for r in results if r.category == category]
        if since is not None:
            results = [r for r in results if r.occurred_at >= since]
        if until is not None:
            results = [r for r in results if r.occurred_at <= until]
        if contains is not None:
            needle = contains.lower()
            results = [r for r in results if (r.content or "").lower().find(needle) != -1]
        return results
