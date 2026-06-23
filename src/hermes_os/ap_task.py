"""AP Task payload schema with strong validation for the Hermes OS bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class APTaskMetadata(BaseModel):
    model_config = {"extra": "ignore"}

    source: Optional[str] = Field(default=None, description="Origin of this task")
    tags: List[str] = Field(default_factory=list, description="Free labels for filtering")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured data")


@dataclass(frozen=True)
class APTask:
    task_id: str
    task_type: str = "task"
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None

    def normalized(self) -> "APTask":
        meta_obj = APTaskMetadata(**(self.metadata or {}))
        return APTask(
            task_id=str(self.task_id),
            task_type=str(self.task_type),
            priority=max(0, int(self.priority)),
            status=self.status,
            payload=dict(self.payload or {}),
            metadata=meta_obj.model_dump(),
        )


def to_ap_task(workforce_item: Dict[str, Any]) -> APTask:
    raw_priority = int(workforce_item.get("priority", 0))
    return APTask(
        task_id=str(workforce_item["id"]),
        task_type=str(workforce_item.get("type", "task")),
        priority=max(0, raw_priority),
        payload=dict(workforce_item.get("payload", {}) or {}),
        metadata=dict(workforce_item.get("metadata", {}) or {}),
    )
