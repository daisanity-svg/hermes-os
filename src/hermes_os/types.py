"""Hermes OS — shared type contracts for MVP modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RunStatus(str, Enum):
    """Canonical run lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    STOPPING = "stopping"


class ActionStatus(str, Enum):
    """Operational action execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_FOR_APPROVAL = "waiting_for_approval"


@dataclass(frozen=True)
class ArtifactRef:
    """Registered artifact descriptor."""

    artifact_id: str
    run_id: str
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    absolute_path: Optional[str] = None
    sha256: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OwnershipRecord:
    """Ownership attribution for an artifact or run."""

    record_id: str
    subject_id: str
    owner: str
    source: str
    granted_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LifecycleEvent:
    """Single lifecycle state transition event."""

    event_id: str
    subject_id: str
    from_status: Optional[str]
    to_status: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    actor: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionRecord:
    """Observable operational action record."""

    action_id: str
    run_id: Optional[str]
    action_type: str
    status: ActionStatus = ActionStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    output_snapshot: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class WorkforceItem:
    """Enqueued workforce/work item descriptor."""

    item_id: str
    item_type: str
    priority: int = 0
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlCenterSnapshot:
    """Point-in-time control center state snapshot."""

    snapshot_id: str
    captured_at: datetime = field(default_factory=datetime.utcnow)
    active_runs: int = 0
    queued_items: int = 0
    failed_items: int = 0
    health_status: str = "unknown"
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryLogEntry:
    """Operational memory log entry."""

    entry_id: str
    source: str
    category: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunJournalEntry:
    """Persistent run journal entry for reliability tracking."""

    run_id: str
    task_name: str
    status: str = "queued"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_event: Optional[str] = None
    error: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    next_action: Optional[str] = None
    retry_count: int = 0
