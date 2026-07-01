"""Reliability Recovery — schemas for Recovery Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class RecoveryStatus(str, Enum):
    """Recovery lifecycle states."""

    FAILED = "failed"
    LOST = "lost"
    STALE = "stale"
    RETRYABLE = "retryable"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    NEEDS_FOUNDER_DECISION = "needs_founder_decision"


@dataclass(frozen=True)
class RetryPolicy:
    """Defines retry behavior and stale thresholds."""

    max_retries: int = 3
    recoverable_errors: tuple = (
        "HTTP 500",
        "HTTP 503",
        "timeout",
        "connection_error",
    )
    max_stale_seconds: int = 3600


@dataclass(frozen=True)
class RecoverableRun:
    """A journal entry classified as actionable by the Recovery Manager."""

    run_id: str
    task_name: str
    current_status: str
    recovery_status: RecoveryStatus
    reason: str
    retry_count: int = 0
    updated_at: datetime = field(default_factory=datetime.utcnow)
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    ticket_id: Optional[str] = None


@dataclass(frozen=True)
class RecoveryTicket:
    """Recovery ticket (equivalent to FounderDecisionTicket for recovery scope)."""

    ticket_id: str
    run_id: str
    priority: str
    title: str
    summary: str
    reason: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    options: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
