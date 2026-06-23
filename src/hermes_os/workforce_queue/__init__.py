"""Workforce Queue — queued work items for the runtime workforce."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from hermes_os.types import WorkforceItem


class WorkforceQueue:
    """MVP skeleton: priority workforce queue."""

    def __init__(self) -> None:
        self._items: dict[str, WorkforceItem] = {}
        self._order: List[str] = []

    def enqueue(
        self,
        item_type: str,
        payload: Optional[Dict[str, object]] = None,
        priority: int = 0,
    ) -> WorkforceItem:
        item = WorkforceItem(
            item_id=f"wq_{len(self._order) + 1}",
            item_type=item_type,
            priority=priority,
            payload=payload or {},
        )
        self._items[item.item_id] = item
        self._order.append(item.item_id)
        self._sort()
        return item

    def dequeue(self) -> Optional[WorkforceItem]:
        while self._order:
            item_id = self._order.pop(0)
            item = self._items.get(item_id)
            if item and item.status == "pending":
                self._items[item_id] = WorkforceItem(
                    item_id=item.item_id,
                    item_type=item.item_type,
                    priority=item.priority,
                    status="running",
                    created_at=item.created_at,
                    payload=item.payload,
                )
                return self._items[item_id]
        return None

    def complete(self, item_id: str) -> Optional[WorkforceItem]:
        item = self._items.get(item_id)
        if item is None:
            return None
        self._items[item_id] = WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=item.priority,
            status="completed",
            created_at=item.created_at,
            payload=item.payload,
        )
        return self._items[item_id]

    def get(self, item_id: str) -> Optional[WorkforceItem]:
        return self._items.get(item_id)

    def pending(self) -> List[WorkforceItem]:
        return [i for i in self._items.values() if i.status == "pending"]

    def count(self) -> int:
        return len(self._items)

    def _sort(self) -> None:
        self._order.sort(key=lambda item_id: -self._items[item_id].priority)
