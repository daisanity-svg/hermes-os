"""Workforce Queue — sorted priority queue for work items."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from hermes_os.types import WorkforceItem


class WorkforceQueue:
    def __init__(self) -> None:
        self._items: Dict[str, WorkforceItem] = {}
        self._queue: List[WorkforceItem] = []

    # ------------------------------------------------------------------
    # mutation
    # ------------------------------------------------------------------
    def enqueue(self, item: WorkforceItem) -> WorkforceItem:
        if item.item_id in self._items:
            raise ValueError(f"duplicate workforce item id: {item.item_id}")
        self._items[item.item_id] = item
        self._insert_sorted(item)
        return item

    def dequeue(self) -> Optional[WorkforceItem]:
        while self._queue:
            candidate = self._queue.pop(0)
            self._items.pop(candidate.item_id, None)
            return candidate
        return None

    def complete(self, item_id: str) -> Optional[WorkforceItem]:
        item = self._items.pop(item_id, None)
        if item is None:
            return None
        return WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=item.priority,
            status="completed",
            created_at=item.created_at,
            payload=item.payload,
        )

    def cancel(self, item_id: str) -> Optional[WorkforceItem]:
        item = self._items.pop(item_id, None)
        if item is None:
            return None
        try:
            idx = self._queue.index(item)
        except ValueError:
            idx = None
        if idx is not None:
            self._queue.pop(idx)
        return WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=item.priority,
            status="cancelled",
            created_at=item.created_at,
            payload=item.payload,
        )

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def pending(self) -> List[WorkforceItem]:
        return [item for item in self._queue if item.item_id in self._items]

    def get(self, item_id: str) -> Optional[WorkforceItem]:
        return self._items.get(item_id)

    def peek(self) -> Optional[WorkforceItem]:
        for candidate in self._queue:
            if candidate.item_id in self._items:
                return candidate
        return None

    def __len__(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _insert_sorted(self, item: WorkforceItem) -> None:
        key = (-item.priority, item.created_at, item.item_id)
        lo, hi = 0, len(self._queue)
        while lo < hi:
            mid = (lo + hi) // 2
            mid_key = (
                -self._queue[mid].priority,
                self._queue[mid].created_at,
                self._queue[mid].item_id,
            )
            if mid_key < key:
                lo = mid + 1
            else:
                hi = mid
        self._queue.insert(lo, item)
