"""Operational Memory Log — append-only operational memory."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from hermes_os.types import MemoryLogEntry


class OperationalMemoryLog:
    """MVP skeleton: in-memory operational memory log."""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryLogEntry] = {}
        self._order: List[str] = []

    def append(
        self,
        source: str,
        category: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> MemoryLogEntry:
        entry = MemoryLogEntry(
            entry_id=f"mem_{len(self._order) + 1}",
            source=source,
            category=category,
            content=content,
            metadata=metadata or {},
        )
        self._entries[entry.entry_id] = entry
        self._order.append(entry.entry_id)
        return entry

    def get(self, entry_id: str) -> Optional[MemoryLogEntry]:
        return self._entries.get(entry_id)

    def query(
        self,
        category: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryLogEntry]:
        results: List[MemoryLogEntry] = []
        for entry_id in reversed(self._order):
            entry = self._entries[entry_id]
            if category and entry.category != category:
                continue
            if source and entry.source != source:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def count(self) -> int:
        return len(self._entries)
