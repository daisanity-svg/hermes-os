"""Recovery Manager — minimal run recovery engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from hermes_os.recovery.schemas import (
    RecoveryStatus,
    RecoverableRun,
    RetryPolicy,
)
from hermes_os.run_journal import RunJournal
from hermes_os.types import RunJournalEntry


class RecoveryManager:
    """最小 Recovery Manager，讀取 Run Journal 並推動狀態恢復。"""

    def __init__(self, journal: RunJournal, policy: Optional[RetryPolicy] = None) -> None:
        self.journal = journal
        self.policy = policy or RetryPolicy()

    def _classify(self, entry: RunJournalEntry) -> Optional[RecoveryStatus]:
        if entry.status == "completed":
            return None
        if entry.status == "failed":
            error_text = (entry.error or "").lower()
            if "run_not_found" in error_text or "not found" in error_text:
                return RecoveryStatus.LOST
            if any(
                kw in error_text
                for kw in ("http 500", "http 503", "timeout", "connection_error")
            ):
                if entry.retry_count < self.policy.max_retries:
                    return RecoveryStatus.RETRYABLE
                return RecoveryStatus.NEEDS_FOUNDER_DECISION
            return RecoveryStatus.FAILED
        if entry.status in ("running", "recovering", "needs_founder_decision"):
            now = datetime.now(timezone.utc)
            last = entry.updated_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age = (now - last).total_seconds()
            if age > self.policy.max_stale_seconds:
                return RecoveryStatus.STALE
            if entry.status == "recovering":
                return RecoveryStatus.RECOVERING
            if entry.status == "needs_founder_decision":
                return RecoveryStatus.NEEDS_FOUNDER_DECISION
        return None

    def list_recoverable(
        self,
        project_code: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RecoverableRun]:
        """列出可恢復的 run entries。"""
        results: List[RecoverableRun] = []
        for entry in self.journal.list():
            status = self._classify(entry)
            if status is None:
                continue
            results.append(
                RecoverableRun(
                    run_id=entry.run_id,
                    task_name=entry.task_name,
                    current_status=entry.status,
                    recovery_status=status,
                    reason=entry.error or "stale run",
                    retry_count=entry.retry_count,
                    updated_at=entry.updated_at,
                    project_code=entry.project_code,
                    project_name=entry.project_name,
                )
            )
        if project_code is not None:
            results = [r for r in results if r.project_code == project_code]
        if limit is not None:
            results = results[-limit:]
        return results

    def mark_recovering(self, run_id: str, reason: str = "retry") -> Optional[RunJournalEntry]:
        """標記 run 為 recovering，遞增 retry_count。"""
        entry = self.journal.get(run_id)
        if entry is None:
            return None
        new_retry = entry.retry_count + 1
        return self.journal.update(
            run_id,
            status="recovering",
            last_event=f"recovery: retry={new_retry}, reason={reason}",
            retry_count=new_retry,
        )

    def mark_recovered(self, run_id: str) -> Optional[RunJournalEntry]:
        """標記 run 為 recovered，重設 retry_count。"""
        return self.journal.update(
            run_id,
            status="completed",
            last_event="recovery: recovered",
            next_action="none",
            retry_count=0,
        )

    def escalate(self, run_id: str, reason: str) -> Optional[dict]:
        """升級 run 至 needs_founder_decision 並產生 recovery ticket。"""
        entry = self.journal.get(run_id)
        if entry is None:
            return None
        ticket_id = f"recovery-{run_id}-{int(datetime.now(timezone.utc).timestamp())}"
        updated = self.journal.update(
            run_id,
            status="needs_founder_decision",
            last_event=f"escalated: {reason}",
            retry_count=entry.retry_count,
        )
        if updated is None:
            return None
        from hermes_os.recovery.schemas import RecoveryTicket
        ticket = RecoveryTicket(
            ticket_id=ticket_id,
            run_id=run_id,
            priority="high",
            title=f"Run recovery escalation: {entry.task_name}",
            summary=f"Run {run_id} requires founder decision after {entry.retry_count} retries.",
            reason=reason,
            options=["retry", "abort", "delegate"],
            metadata={"recovery": True, "run_id": run_id, "project_code": entry.project_code},
        )
        return {
            "ticket_id": ticket.ticket_id,
            "run_id": ticket.run_id,
            "priority": ticket.priority,
            "title": ticket.title,
            "summary": ticket.summary,
            "reason": ticket.reason,
            "created_at": ticket.created_at.isoformat(),
            "options": ticket.options,
            "metadata": ticket.metadata,
            "source": "recovery-manager",
        }
