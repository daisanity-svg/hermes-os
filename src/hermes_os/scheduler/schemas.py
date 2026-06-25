"""Hermes OS — Auto Scheduler v1 schemas & dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TaskPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TaskStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    PAUSED = "paused"


class FounderDecisionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SchedulerSource(str, Enum):
    PROJECT_STATUS = "project-status"
    CONTRACTS_INDEX = "contracts-index"
    PACKAGES = "packages"
    RUNS = "runs"
    FOUNDER_INBOX = "founder-inbox"
    WATCHDOG = "watchdog"


@dataclass(frozen=True)
class FounderDecisionTicket:
    """Human decision request emitted by Scheduler."""

    ticket_id: str
    priority: FounderDecisionPriority
    source: SchedulerSource
    title: str
    summary: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = None
    options: List[str] = field(default_factory=list)
    blocking_item_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TaskCandidate:
    """One schedulable candidate."""

    item_id: str
    title: str
    priority: TaskPriority
    source: SchedulerSource
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = field(default_factory=list)
    auto_start: bool = False
    sla_finish_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    drift_count: int = 0
    last_watchdog_stagnant_checks: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WatchdogSignal:
    """Stagnation / health notice from Watchdog."""

    item_id: str
    consecutive_idle_checks: int
    health_status: str
    last_seen_at: datetime
    detected_at: datetime = field(default_factory=datetime.utcnow)
    suggested_action: str = ""


@dataclass(frozen=True)
class SortedTaskQueue:
    """Result of Scheduler.propose()."""

    proposed_at: datetime = field(default_factory=datetime.utcnow)
    executable: List[TaskCandidate] = field(default_factory=list)
    blocked: List[TaskCandidate] = field(default_factory=list)
    waiting_founder: List[TaskCandidate] = field(default_factory=list)
    founder_decisions: List[FounderDecisionTicket] = field(default_factory=list)


@dataclass(frozen=True)
class ScheduleAuditEntry:
    """Single audit log entry."""

    entry_id: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    action: str = ""
    source: str = ""
    detail: str = ""
    proposed_queue_length: int = 0


@dataclass(frozen=True)
class AutoSchedulerConfig:
    """Scheduler configuration."""

    max_concurrent: int = 3
    drift_threshold_hours: int = 4
    watchdog_idle_warn: int = 3
    watchdog_idle_block: int = 6
    watchdog_degraded_threshold: int = 5
