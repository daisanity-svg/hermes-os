"""Workforce Queue — sorted priority queue for work items."""

from __future__ import annotations

import time
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
    def enqueue(self, item: WorkforceItem, ttl_seconds: Optional[int] = None) -> WorkforceItem:
        if item.item_id in self._items:
            raise ValueError(f"duplicate workforce item id: {item.item_id}")
        if ttl_seconds is not None:
            item.payload["_ttl_expires_at"] = time.time() + ttl_seconds
        self._items[item.item_id] = item
        self._insert_sorted(item)
        return item

    def dequeue(self) -> Optional[WorkforceItem]:
        self._expire()
        while self._queue:
            candidate = self._queue.pop(0)
            if candidate.item_id in self._items:
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

    def expire(self, item_id: str) -> Optional[WorkforceItem]:
        return self.cancel(item_id)

    def set_priority(self, item_id: str, priority: int) -> Optional[WorkforceItem]:
        item = self._items.get(item_id)
        if item is None:
            return None
        updated = WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=int(priority),
            status=item.status,
            created_at=item.created_at,
            payload=item.payload,
        )
        self.cancel(item_id)
        self.enqueue(updated)
        return updated

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def pending(self) -> List[WorkforceItem]:
        self._expire()
        return [item for item in self._queue if item.item_id in self._items]

    def get(self, item_id: str) -> Optional[WorkforceItem]:
        return self._items.get(item_id)

    def peek(self) -> Optional[WorkforceItem]:
        self._expire()
        for candidate in self._queue:
            if candidate.item_id in self._items:
                return candidate
        return None

    def __len__(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _expire(self) -> None:
        now = time.time()
        expired = [
            item_id
            for item_id, item in list(self._items.items())
            if item.payload.get("_ttl_expires_at") is not None
            and float(item.payload.get("_ttl_expires_at")) <= now
        ]
        for item_id in expired:
            self.cancel(item_id)

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
