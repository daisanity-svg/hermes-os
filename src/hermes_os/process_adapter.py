"""Hermes OS → Hermes Agent Process Adapter."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from hermes_os.event_bus import DomainEvent, EventBus
from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


class _ShutdownRequested(Exception):
    pass


class _TimedOut(Exception):
    pass


class ProcessAdapter:
    def __init__(
        self,
        max_retries: int = 3,
        base_backoff_seconds: float = 0.5,
        circuit_failure_threshold: int = 5,
        circuit_recovery_seconds: float = 2.0,
        drain_timeout_seconds: float = 1.0,
        execution_timeout_seconds: Optional[float] = None,
        retry_hook: Optional[Callable[..., None]] = None,
    ) -> None:
        self.queue = WorkforceQueue()
        self.memory = OperationalMemoryLog()
        self.events = EventBus()
        self._context: Dict[str, Any] = {}
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._run_registry: Dict[str, Dict[str, Any]] = {}
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_recovery_seconds = circuit_recovery_seconds
        self._circuit_until: Dict[str, datetime] = {}
        self.drain_timeout_seconds = drain_timeout_seconds
        self.execution_timeout_seconds = execution_timeout_seconds
        self.retry_hook = retry_hook
        self._shutdown_requested = False
        self._draining = False

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _publish(self, name: str, entry: Dict[str, Any]) -> None:
        if self._shutdown_requested and not self._draining:
            raise _ShutdownRequested()
        event = DomainEvent(name=name, source="adapter", occurred_at=self._now(), payload=entry)
        self.memory.append(
            source="adapter",
            category="event",
            content=f"{name} {entry.get('workforce_item_id', '')}".strip(),
            metadata={"event_name": name, "payload": entry},
        )
        self.events.publish(event)

    def request_shutdown(self) -> None:
        self._shutdown_requested = True

    def shutdown(self) -> Dict[str, Any]:
        self.request_shutdown()
        self._draining = True
        deadline = self._now() + timedelta(seconds=self.drain_timeout_seconds)
        drained: List[Dict[str, Any]] = []
        try:
            while self._now() < deadline:
                batch = self.drain(limit=max(1, len(self.queue)))
                if not batch:
                    break
                drained.extend(batch)
        finally:
            self._draining = False
        return {
            "status": "shutdown",
            "drained_count": len(drained),
            "deadline_reached": self._now() >= deadline,
        }

    def submit(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if self._shutdown_requested:
            raise _ShutdownRequested()
        created_at = self._now()
        parent_id = item.get("parent_id")
        parent_entry = self._run_registry.get(parent_id) if parent_id else None
        priority = int(item.get("priority", parent_entry["priority"])) if parent_entry else int(item.get("priority", 0))
        workforce_item = WorkforceItem(
            item_id=item["id"],
            item_type=item.get("type", "task"),
            priority=priority,
            status="queued",
            created_at=created_at,
            payload=item.get("payload", {}),
        )
        self.queue.enqueue(workforce_item)
        self._run_registry[workforce_item.item_id] = {
            "submitted_at": created_at.isoformat(),
            "priority": workforce_item.priority,
            "parent_id": parent_id,
            "group_id": item.get("group_id"),
            "retry_count": 0,
            "status": "queued",
            "status_updated_at": created_at.isoformat(),
            "output": {},
            "error": None,
            "failure_count": 0,
            "started_at": None,
            "finished_at": None,
        }
        entry = {"workforce_item_id": workforce_item.item_id, "group_id": item.get("group_id")}
        self._publish("submitted", entry)
        return {
            **entry,
            "status": "queued",
            "priority": workforce_item.priority,
            "retry_count": 0,
            "submitted_at": self._run_registry[workforce_item.item_id]["submitted_at"],
        }

    def batch_submit(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.submit(item) for item in items]

    def _expire_if_timed_out(self, item_id: str) -> bool:
        if self.execution_timeout_seconds is None:
            return False
        entry = self._run_registry.get(item_id, {})
        started_at = entry.get("started_at")
        if not started_at:
            return False
        started = datetime.fromisoformat(started_at)
        if self._now() - started > timedelta(seconds=self.execution_timeout_seconds):
            self.record_failure(item_id, error="execution_timeout", retry=False)
            return True
        return False

    def drain(self, limit: int = 1) -> List[Dict[str, Any]]:
        drained: List[Dict[str, Any]] = []
        selected: List[WorkforceItem] = []
        for _ in range(limit):
            item = self.queue.dequeue()
            if item is None:
                break
            selected.append(item)
        now = self._now()
        for item in selected:
            entry = self._run_registry.setdefault(item.item_id, {})
            entry["status"] = "running"
            entry.setdefault("started_at", now.isoformat())
            entry["status_updated_at"] = now.isoformat()
            self._publish("started", {"workforce_item_id": item.item_id})
            if self._expire_if_timed_out(item.item_id):
                entry["status"] = "failed"
                entry["finished_at"] = now.isoformat()
                entry["status_updated_at"] = now.isoformat()
                drained.append(
                    {
                        "id": item.item_id,
                        "type": item.item_type,
                        "priority": item.priority,
                        "status": "failed",
                        "payload": item.payload,
                    }
                )
                continue
            entry["status"] = "completed"
            entry["finished_at"] = now.isoformat()
            entry["status_updated_at"] = now.isoformat()
            drained.append(
                {
                    "id": item.item_id,
                    "type": item.item_type,
                    "priority": item.priority,
                    "status": "completed",
                    "payload": item.payload,
                }
            )
        if drained:
            payload = {"drained_count": len(drained)}
            self._publish("drained", payload)
        return drained

    def complete(self, item_id: str) -> Dict[str, Any]:
        now = self._now()
        item = self.queue.complete(item_id)
        entry = self._run_registry.get(item_id, {})
        if item is None:
            entry["status"] = "not_found"
            entry["status_updated_at"] = now.isoformat()
            entry["error"] = entry.get("error") or "not_found"
            return {
                "workforce_item_id": item_id,
                "status": "not_found",
                "retry_count": entry.get("retry_count", 0),
                "error": entry.get("error"),
                "updated_at": entry.get("status_updated_at"),
            }
        entry["status"] = "completed"
        entry["finished_at"] = now.isoformat()
        entry["status_updated_at"] = now.isoformat()
        entry.pop("circuit_open", None)
        payload = {"workforce_item_id": item.item_id}
        self._publish("completed", payload)
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
        payload = {
            "workforce_item_id": item_id,
            "priority": entry["priority"],
            "updated_at": entry["status_updated_at"],
        }
        self._publish("priority_updated", payload)
        return {**payload, "status": "requeued"}

    def record_failure(self, item_id: str, error: Optional[str] = None, retry: bool = False) -> Dict[str, Any]:
        entry = self._run_registry.setdefault(item_id, {})
        retry_count = int(entry.get("retry_count", 0))
        failure_count = int(entry.get("failure_count", 0)) + 1
        entry["failure_count"] = failure_count
        entry["error"] = error
        entry["last_error"] = error
        if failure_count >= self.circuit_failure_threshold:
            entry["circuit_open"] = True
            entry["circuit_open_until"] = (self._now() + timedelta(seconds=self.circuit_recovery_seconds)).isoformat()
            self._circuit_until[item_id] = self._now() + timedelta(seconds=self.circuit_recovery_seconds)
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
            payload = {
                "workforce_item_id": item_id,
                "retry_count": retry_count,
                "backoff_seconds": backoff,
                "updated_at": entry.get("status_updated_at"),
            }
            if self.retry_hook is not None:
                self.retry_hook(self, item_id, entry, retry_count=retry_count, backoff_seconds=backoff)
            self._publish("retry", payload)
            return {**payload, "status": "retry"}
        entry["status"] = "failed"
        entry["status_updated_at"] = self._now().isoformat()
        payload = {
            "workforce_item_id": item_id,
            "retry_count": retry_count,
            "error": error,
            "updated_at": entry.get("status_updated_at"),
        }
        self._publish("failed", payload)
        return {**payload, "status": "failed"}

    def retry(self, item_id: str) -> Optional[Dict[str, Any]]:
        entry = self._run_registry.get(item_id)
        if not entry:
            return None
        if entry.get("circuit_open") and self._now() < self._circuit_until.get(item_id, self._now()):
            return {
                "workforce_item_id": item_id,
                "status": "circuit_open",
                "retry_count": entry.get("retry_count", 0),
                "updated_at": entry.get("status_updated_at"),
            }
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
        entry["circuit_open"] = False
        entry.pop("circuit_open_until", None)
        entry["status_updated_at"] = self._now().isoformat()
        entry["backoff_seconds"] = backoff
        payload = {
            "workforce_item_id": item_id,
            "retry_count": retry_count,
            "backoff_seconds": backoff,
            "updated_at": entry.get("status_updated_at"),
        }
        self._publish("retried", payload)
        return {**payload, "status": "queued"}

    def cancel_by_filter(self, max_age_seconds: Optional[int] = None, max_priority: Optional[int] = None) -> List[Dict[str, Any]]:
        cancelled: List[Dict[str, Any]] = []
        candidates = list(self._run_registry.items())
        submitted_since = self._now() - timedelta(seconds=max_age_seconds) if max_age_seconds is not None else None
        for item_id, entry in candidates:
            item = self.queue.get(item_id)
            if item is None:
                continue
            if submitted_since is not None:
                submitted_at = datetime.fromisoformat(entry.get("submitted_at", self._now().isoformat()))
                if submitted_at > submitted_since:
                    continue
            if max_priority is not None and item.priority > max_priority:
                continue
            self.queue.cancel(item_id)
            entry["status"] = "cancelled"
            entry["status_updated_at"] = self._now().isoformat()
            payload = {"workforce_item_id": item_id}
            cancelled.append({**payload, "status": "cancelled"})
            self._publish("cancelled", payload)
        return cancelled

    def list_by_group(self, group_id: str) -> Dict[str, Any]:
        items = []
        for item_id, entry in self._run_registry.items():
            if entry.get("group_id") != group_id:
                continue
            item = self.queue.get(item_id)
            items.append(
                {
                    "workforce_item_id": item_id,
                    "status": entry.get("status"),
                    "priority": entry.get("priority"),
                    "group_id": entry.get("group_id"),
                    "item": {
                        "item_id": item.item_id if item else item_id,
                        "item_type": item.item_type if item else None,
                        "priority": item.priority if item else None,
                        "status": item.status if item else None,
                    }
                    if item
                    else None,
                }
            )
        return {"group_id": group_id, "items": items}
