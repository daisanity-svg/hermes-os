"""Hermes OS → Hermes Agent Process Adapter."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


class ProcessAdapter:
    def __init__(self, max_retries: int = 3, base_backoff_seconds: float = 0.5) -> None:
        self.queue = WorkforceQueue()
        self.memory = OperationalMemoryLog()
        self._context: Dict[str, Any] = {}
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._run_registry: Dict[str, Dict[str, Any]] = {}

    def _now(self) -> datetime:
        return datetime.utcnow()

    def submit(self, item: Dict[str, Any]) -> Dict[str, Any]:
        workforce_item = WorkforceItem(
            item_id=item["id"],
            item_type=item.get("type", "task"),
            priority=int(item.get("priority", 0)),
            status="pending",
            created_at=self._now(),
            payload=item.get("payload", {}),
        )
        self.queue.enqueue(workforce_item)
        self._run_registry[workforce_item.item_id] = {
            "submitted_at": self._now().isoformat(),
            "priority": workforce_item.priority,
            "retry_count": 0,
            "status": "queued",
            "status_updated_at": self._now().isoformat(),
            "output": {},
            "error": None,
        }
        self.memory.append(
            source="adapter",
            category="submission",
            content=f"submitted {workforce_item.item_id}",
            metadata={"workforce_item_id": workforce_item.item_id},
        )
        return {
            "workforce_item_id": workforce_item.item_id,
            "status": "queued",
            "priority": workforce_item.priority,
            "retry_count": 0,
            "submitted_at": self._run_registry[workforce_item.item_id]["submitted_at"],
        }

    def batch_submit(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.submit(item) for item in items]

    def drain(self, limit: int = 1) -> List[Dict[str, Any]]:
        drained: List[Dict[str, Any]] = []
        for _ in range(limit):
            item = self.queue.dequeue()
            if item is None:
                break
            entry = self._run_registry.get(item.item_id, {})
            entry.setdefault("status", "completed")
            entry["status_updated_at"] = self._now().isoformat()
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

    def complete(self, item_id: str) -> Dict[str, Any]:
        item = self.queue.complete(item_id)
        entry = self._run_registry.get(item_id, {})
        if item is None:
            entry["status"] = "not_found"
            entry["status_updated_at"] = self._now().isoformat()
            entry["error"] = entry.get("error") or "not_found"
            return {
                "workforce_item_id": item_id,
                "status": "not_found",
                "retry_count": entry.get("retry_count", 0),
                "error": entry.get("error"),
                "updated_at": entry.get("status_updated_at"),
            }
        entry["status"] = "completed"
        entry["status_updated_at"] = self._now().isoformat()
        self.memory.append(
            source="adapter",
            category="completion",
            content=f"completed {item.item_id}",
            metadata={"workforce_item_id": item.item_id},
        )
        return {
            "workforce_item_id": item.item_id,
            "status": "completed",
            "retry_count": entry.get("retry_count", 0),
            "updated_at": entry.get("status_updated_at"),
        }

    def set_priority(self, item_id: str, priority: int) -> Dict[str, Any]:
        entry = self._run_registry.get(item_id)
        if entry is None:
            return {"workforce_item_id": item_id, "status": "not_found"}
        item = self.queue.get(item_id)
        if item is None:
            return {"workforce_item_id": item_id, "status": "not_found"}
        entry["priority"] = int(priority)
        entry["last_status_update_reason"] = "priority_updated"
        entry["status_updated_at"] = self._now().isoformat()
        updated = WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=entry["priority"],
            status=item.status,
            created_at=item.created_at,
            payload=item.payload,
        )
        self.queue.cancel(item_id)
        self.queue.enqueue(updated)
        return {
            "workforce_item_id": item_id,
            "status": "requeued",
            "priority": entry["priority"],
            "updated_at": entry["status_updated_at"],
        }

    def record_failure(self, item_id: str, error: Optional[str] = None, retry: bool = False) -> Dict[str, Any]:
        entry = self._run_registry.get(item_id, {})
        retry_count = int(entry.get("retry_count", 0))
        entry["error"] = error
        entry["last_error"] = error
        if retry and retry_count < self.max_retries:
            retry_count += 1
            entry["retry_count"] = retry_count
            entry["status"] = "retry"
            backoff = math.pow(2, retry_count) * self.base_backoff_seconds
            item = self.queue.get(item_id)
            if item is not None:
                updated = WorkforceItem(
                    item_id=item.item_id,
                    item_type=item.item_type,
                    priority=item.priority,
                    status="retry",
                    created_at=item.created_at,
                    payload={**item.payload, "retry_count": retry_count, "backoff_seconds": backoff},
                )
                self.queue.cancel(item_id)
                self.queue.enqueue(updated)
            entry["backoff_seconds"] = backoff
            entry["status_updated_at"] = self._now().isoformat()
            return {
                "workforce_item_id": item_id,
                "status": "retry",
                "retry_count": retry_count,
                "backoff_seconds": backoff,
                "updated_at": entry.get("status_updated_at"),
            }
        entry["status"] = "failed"
        entry["status_updated_at"] = self._now().isoformat()
        return {
            "workforce_item_id": item_id,
            "status": "failed",
            "retry_count": retry_count,
            "error": error,
            "updated_at": entry.get("status_updated_at"),
        }

    def retry(self, item_id: str) -> Optional[Dict[str, Any]]:
        entry = self._run_registry.get(item_id)
        if not entry:
            return None
        retry_count = int(entry.get("retry_count", 0)) + 1
        entry["retry_count"] = retry_count
        backoff = math.pow(2, retry_count) * self.base_backoff_seconds
        item = self.queue.get(item_id)
        if item is None:
            return None
        updated = WorkforceItem(
            item_id=item.item_id,
            item_type=item.item_type,
            priority=item.priority,
            status="queued",
            created_at=item.created_at,
            payload={**item.payload, "retry_count": retry_count, "backoff_seconds": backoff},
        )
        self.queue.cancel(item_id)
        self.queue.enqueue(updated)
        entry["status"] = "queued"
        entry["status_updated_at"] = self._now().isoformat()
        entry["backoff_seconds"] = backoff
        return {
            "workforce_item_id": item_id,
            "status": "queued",
            "retry_count": retry_count,
            "backoff_seconds": backoff,
            "updated_at": entry.get("status_updated_at"),
        }
