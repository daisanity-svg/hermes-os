"""Hermes OS → Hermes Agent Process Adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


class ProcessAdapter:
    def __init__(self) -> None:
        self.queue = WorkforceQueue()
        self.memory = OperationalMemoryLog()
        self._context: Dict[str, Any] = {}

    def submit(self, item: Dict[str, Any]) -> Dict[str, Any]:
        workforce_item = WorkforceItem(
            item_id=item["id"],
            item_type=item.get("type", "task"),
            priority=int(item.get("priority", 0)),
            status="pending",
            created_at=datetime.utcnow(),
            payload=item.get("payload", {}),
        )
        self.queue.enqueue(workforce_item)
        self.memory.append(
            source="adapter",
            category="submission",
            content=f"submitted {workforce_item.item_id}",
            metadata={"workforce_item_id": workforce_item.item_id},
        )
        return {"workforce_item_id": workforce_item.item_id, "status": "queued"}

    def drain(self, limit: int = 1) -> List[Dict[str, Any]]:
        drained: List[Dict[str, Any]] = []
        for _ in range(limit):
            item = self.queue.dequeue()
            if item is None:
                break
            drained.append(
                {
                    "id": item.item_id,
                    "type": item.item_type,
                    "priority": item.priority,
                    "payload": item.payload,
                }
            )
        if drained:
            self.memory.append(
                source="adapter",
                category="process",
                content=f"drained {len(drained)} workforce items",
                metadata={"drained_count": len(drained)},
            )
        return drained
