"""Hermes OS → Hermes Agent Process Adapter."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from hermes_os.event_bus import DomainEvent, EventBus
from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem
from hermes_os.workflow_records import WorkflowRecords
from hermes_os.approval_records import ApprovalRecords
from hermes_os.run_params_records import RunParamsRecords
from hermes_os.run_journal import RunJournal
from hermes_os.run_registry import RunRegistry
from hermes_os.run_journal_jsonl import JsonlRunJournal

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
        sla_seconds: Optional[float] = None,
        on_complete: Optional[Callable[..., None]] = None,
        workflow_records: Optional["WorkflowRecords"] = None,
        approval_records: Optional["ApprovalRecords"] = None,
        run_params_records: Optional["RunParamsRecords"] = None,
        journal: Optional[RunJournal] = None,
    ) -> None:
        self.queue = WorkforceQueue()
        self.memory = OperationalMemoryLog()
        self.events = EventBus()
        self._context: Dict[str, Any] = {}
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._run_registry: Dict[str, Dict[str, Any]] = {}
        self._run_metadata: Dict[str, Dict[str, Any]] = {}
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_recovery_seconds = circuit_recovery_seconds
        self._circuit_until: Dict[str, datetime] = {}
        self.drain_timeout_seconds = drain_timeout_seconds
        self.execution_timeout_seconds = execution_timeout_seconds
        self.retry_hook = retry_hook
        self.sla_seconds = sla_seconds
        self.on_complete = on_complete
        self.workflow_records = workflow_records
        self.approval_records = approval_records
        self.run_params_records = run_params_records
        self._journal = journal or RunJournal()
        self._run_registry_sqlite: RunRegistry = RunRegistry()
        self._journal_jsonl: JsonlRunJournal = JsonlRunJournal()
        self._params_registry: Dict[str, Dict[str, Any]] = {}
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
            "workflow_id": item.get("workflow_id"),
            "step_id": item.get("step_id"),
            "approval_status": item.get("approval_status"),
            "run_id": item.get("run_id") or workforce_item.item_id,
            "retry_count": 0,
            "status": "queued",
            "status_updated_at": created_at.isoformat(),
            "output": {},
            "error": None,
            "failure_count": 0,
            "started_at": None,
            "finished_at": None,
            "sla_seconds": self.sla_seconds,
            "sla_exceeded": False,
            "params": item.get("params"),
        }
        run_id = item.get("run_id")
        if run_id:
            run_meta = self._run_metadata.setdefault(
                run_id,
                {
                    "run_id": run_id,
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                    "item_count": 0,
                    "statuses": {},
                },
            )
            run_meta["item_count"] += 1
            run_meta["updated_at"] = created_at.isoformat()
            input_payload = item.get("payload") or item.get("params") or item.get("input")
            self._run_registry_sqlite.upsert(
                run_id=run_id,
                status="queued",
                created_at=created_at,
                task_name=item.get("title") or workforce_item.item_id,
                input_json=input_payload if isinstance(input_payload, dict) else {"raw": input_payload},
            )
            self._journal_jsonl.append(
                run_id=run_id,
                status="queued",
                occurred_at=created_at,
                event="submitted",
                task_name=item.get("title") or workforce_item.item_id,
            )
        journal_run_id = run_id or workforce_item.item_id
        journal_task_name = item.get("title") or workforce_item.item_id
        self._journal.append(
            run_id=journal_run_id,
            task_name=journal_task_name,
            status="queued",
            last_event="submitted",
            project_code=item.get("project_code"),
            project_name=item.get("project_name"),
        )
        entry = {"workforce_item_id": workforce_item.item_id, "group_id": item.get("group_id")}
        return {
            **entry,
            "run_id": run_id or workforce_item.item_id,
            "status": "queued",
            "priority": workforce_item.priority,
            "retry_count": 0,
            "submitted_at": self._run_registry[workforce_item.item_id]["submitted_at"],
            "sla_seconds": self.sla_seconds,
            "sla_exceeded": False,
        }

    def batch_submit(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.submit(item) for item in items]

    def createRun(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return self.submit(item)

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
            self._check_sla(item.item_id)
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
        if self.on_complete is not None:
            self.on_complete(self, item.item_id, entry)
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

    def cancel_by_group(self, group_id: str) -> List[Dict[str, Any]]:
        cancelled: List[Dict[str, Any]] = []
        for item_id, entry in list(self._run_registry.items()):
            if entry.get("group_id") != group_id:
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

    def list_workflows(self) -> List[Dict[str, Any]]:
        if self.workflow_records is None:
            return []
        workflows = []
        for workflow_id, entry in self._run_registry.items():
            workflow_id_value = entry.get("workflow_id")
            if not workflow_id_value:
                continue
            record = self.workflow_records.get(workflow_id_value)
            if record is None:
                continue
            workflows.append(
                {
                    "workflow_id": record.workflow_id,
                    "root_item_id": record.root_item_id,
                    "status": record.status,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )
        return workflows

    def list_for_run(self, run_id: Optional[str]) -> Dict[str, Any]:
        if not run_id:
            return {"run_id": run_id, "items": [], "metadata": {}}
        items = []
        statuses: Dict[str, int] = {}
        for item_id, entry in self._run_registry.items():
            if entry.get("run_id") != run_id:
                continue
            item = self.queue.get(item_id)
            status = entry.get("status")
            if status:
                statuses[status] = statuses.get(status, 0) + 1
            items.append(
                {
                    "workforce_item_id": item_id,
                    "status": status,
                    "priority": entry.get("priority"),
                    "run_id": entry.get("run_id"),
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
        run_meta = self._run_metadata.get(run_id, {})
        return {
            "run_id": run_id,
            "items": items,
            "metadata": {
                "item_count": run_meta.get("item_count", len(items)),
                "statuses": statuses,
                "created_at": run_meta.get("created_at"),
                "updated_at": run_meta.get("updated_at"),
            },
        }

    def update_run_status(self, run_id: str, status: str) -> Optional[Dict[str, Any]]:
        run_meta = self._run_metadata.get(run_id)
        if run_meta is None:
            return None
        run_meta["status"] = status
        run_meta["updated_at"] = self._now().isoformat()
        for item_id, entry in self._run_registry.items():
            if entry.get("run_id") != run_id:
                continue
            entry["status"] = status
            entry["status_updated_at"] = run_meta["updated_at"]
        payload = {"run_id": run_id, "status": status}
        self._publish("run_updated", payload)
        return {**payload, "updated_at": run_meta["updated_at"]}

    def waitRun(self, item_id: str) -> Dict[str, Any]:
        entry = self._run_registry.get(item_id)
        if entry is not None:
            return {
                "workforce_item_id": item_id,
                "status": entry.get("status"),
                "updated_at": entry.get("status_updated_at") or entry.get("updated_at"),
                "found_in": "registry",
            }
        registry_record = self._run_registry_sqlite.get(item_id)
        if registry_record:
            return {
                "workforce_item_id": item_id,
                "status": registry_record.get("status"),
                "updated_at": registry_record.get("updated_at"),
                "found_in": "sqlite_registry",
            }
        jsonl_latest = self._journal_jsonl.latest(item_id)
        if jsonl_latest is not None:
            return {
                "workforce_item_id": item_id,
                "status": jsonl_latest.get("status"),
                "updated_at": jsonl_latest.get("occurred_at"),
                "found_in": "jsonl_journal",
                "last_event": jsonl_latest.get("event"),
            }
        return {
            "workforce_item_id": item_id,
            "status": "run_not_found",
            "found_in": "none",
        }

    @staticmethod
    def _params_fingerprint(params: Optional[Dict[str, Any]]) -> Optional[str]:
        if not params:
            return None
        try:
            import hashlib
            import json

            normalized = json.dumps(params, sort_keys=True, separators=(",", ":"))
            return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        except Exception:
            return None

    def set_run_params(self, run_id: str, params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if params is None:
            return None
        fingerprint = self._params_fingerprint(params)
        existing = self._params_registry.get(run_id)
        if existing and existing.get("fingerprint") == fingerprint:
            return {"run_id": run_id, "params": existing["params"], "deduplicated": True}
        record = None
        if self.run_params_records is not None:
            record = self.run_params_records.set(run_id, params)
        self._params_registry[run_id] = {"params": dict(params), "fingerprint": fingerprint}
        return {
            "run_id": run_id,
            "params": dict(params),
            "deduplicated": False,
            "updated_at": record.updated_at if record else None,
        }

    def get_run_params(self, run_id: str) -> Dict[str, Any]:
        record = self._params_registry.get(run_id)
        if record is None:
            return {"run_id": run_id, "params": {}}
        return {"run_id": run_id, "params": record["params"]}

    def approve(self, item_id: str) -> Optional[Dict[str, Any]]:
        if self.approval_records is None:
            return None
        record = self.approval_records.approve(item_id)
        if record is None:
            return None
        entry = self._run_registry.setdefault(item_id, {})
        entry["approval_status"] = "approved"
        entry["status_updated_at"] = self._now().isoformat()
        payload = {"workforce_item_id": item_id, "approval_status": "approved"}
        self._publish("approved", payload)
        return {**payload, "updated_at": entry["status_updated_at"]}

    def reject(self, item_id: str) -> Optional[Dict[str, Any]]:
        if self.approval_records is None:
            return None
        record = self.approval_records.reject(item_id)
        if record is None:
            return None
        entry = self._run_registry.setdefault(item_id, {})
        entry["approval_status"] = "rejected"
        entry["status_updated_at"] = self._now().isoformat()
        payload = {"workforce_item_id": item_id, "approval_status": "rejected"}
        self._publish("rejected", payload)
        return {**payload, "updated_at": entry["status_updated_at"]}

    def _check_sla(self, item_id: str) -> None:
        if self.sla_seconds is None:
            return
        entry = self._run_registry.get(item_id, {})
        if not entry.get("started_at"):
            return
        started = datetime.fromisoformat(entry["started_at"])
        if self._now() - started > timedelta(seconds=self.sla_seconds) and not entry.get("sla_exceeded"):
            entry["sla_exceeded"] = True
            entry["status_updated_at"] = self._now().isoformat()
            self._publish("sla_exceeded", {"workforce_item_id": item_id})
