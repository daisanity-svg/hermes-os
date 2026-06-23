"""AP Task payload schema for Hermes OS → Hermes Agent bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class APTask:
    """Canonical payload for submitting work from Hermes OS into Hermes Agent."""

    task_id: str
    task_type: str = "task"
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def to_ap_task(workforce_item: Dict[str, Any]) -> APTask:
    raw_priority = int(workforce_item.get("priority", 0))
    return APTask(
        task_id=str(workforce_item["id"]),
        task_type=str(workforce_item.get("type", "task")),
        priority=max(0, raw_priority),
        payload=dict(workforce_item.get("payload", {}) or {}),
        metadata=dict(workforce_item.get("metadata", {}) or {}),
    )
