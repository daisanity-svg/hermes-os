"""Tests for Recovery Manager."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pytest

from hermes_os.run_journal import RunJournal
from hermes_os.recovery import RecoveryManager, RecoveryStatus
from hermes_os.recovery.schemas import RetryPolicy


REPO = Path(__file__).resolve().parents[1]


def _make_journal(tmp_path: Path) -> RunJournal:
    target = tmp_path / "run-journal.json"
    return RunJournal(storage_path=target)


def _make_manager(tmp_path: Path, policy: Optional[RetryPolicy] = None) -> tuple[RunJournal, RecoveryManager]:
    journal = _make_journal(tmp_path)
    mgr = RecoveryManager(journal=journal, policy=policy)
    return journal, mgr


def test_http_500_is_retryable(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r1", task_name="t1", status="failed", error="HTTP 500 Internal Server Error")
    runs = mgr.list_recoverable()
    assert len(runs) == 1
    assert runs[0].recovery_status == RecoveryStatus.RETRYABLE
    assert runs[0].retry_count == 0


def test_http_503_is_retryable(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r2", task_name="t2", status="failed", error="HTTP 503 Service Unavailable")
    runs = mgr.list_recoverable()
    assert len(runs) == 1
    assert runs[0].recovery_status == RecoveryStatus.RETRYABLE


def test_exceed_max_retries_becomes_needs_founder_decision(tmp_path: Path) -> None:
    policy = RetryPolicy(max_retries=2)
    journal, mgr = _make_manager(tmp_path, policy=policy)
    journal.append(run_id="r3", task_name="t3", status="failed", error="HTTP 500", retry_count=2)
    runs = mgr.list_recoverable()
    assert len(runs) == 1
    assert runs[0].recovery_status == RecoveryStatus.NEEDS_FOUNDER_DECISION


def test_run_not_found_is_lost(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r4", task_name="t4", status="failed", error="run_not_found: missing context")
    runs = mgr.list_recoverable()
    assert len(runs) == 1
    assert runs[0].recovery_status == RecoveryStatus.LOST


def test_stale_running_is_stale(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    old_ts = datetime.now(timezone.utc) - timedelta(seconds=4000)
    rid = "r5"
    journal.append(run_id=rid, task_name="t5", status="running")
    journal.update(rid, updated_at=old_ts)
    runs = mgr.list_recoverable()
    assert len(runs) == 1
    assert runs[0].recovery_status == RecoveryStatus.STALE


def test_completed_is_not_recoverable(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r6", task_name="t6", status="completed")
    assert mgr.list_recoverable() == []


def test_mark_recovering_increments_retry(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r7", task_name="t7", status="failed", error="HTTP 500")
    result = mgr.mark_recovering("r7", reason="http_500")
    assert result is not None
    assert result.status == "recovering"
    assert result.retry_count == 1
    assert result.last_event is not None
    assert "retry=1" in result.last_event


def test_mark_recovered_resets_state(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r8", task_name="t8", status="failed", error="HTTP 500", retry_count=2)
    result = mgr.mark_recovered("r8")
    assert result is not None
    assert result.status == "completed"
    assert result.retry_count == 0
    assert result.next_action == "none"


def test_escalate_creates_ticket_and_updates_journal(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r9", task_name="t9", status="failed", error="HTTP 500", retry_count=3)
    ticket = mgr.escalate("r9", reason="max_retries_exceeded")
    assert ticket is not None
    assert ticket["ticket_id"].startswith("recovery-r9-")
    assert ticket["priority"] == "high"
    assert ticket["source"] == "recovery-manager"
    entry = journal.get("r9")
    assert entry is not None
    assert entry.status == "needs_founder_decision"


def test_list_recoverable_filters_by_project(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    journal.append(run_id="r10", task_name="t10", status="failed", error="HTTP 500", project_code="A")
    journal.append(run_id="r11", task_name="t11", status="failed", error="HTTP 500", project_code="B")
    runs = mgr.list_recoverable(project_code="A")
    assert len(runs) == 1
    assert runs[0].project_code == "A"


def test_list_recoverable_limit(tmp_path: Path) -> None:
    journal, mgr = _make_manager(tmp_path)
    for i in range(5):
        journal.append(run_id=f"r{i}", task_name=f"t{i}", status="failed", error="HTTP 500")
    runs = mgr.list_recoverable(limit=2)
    assert len(runs) == 2


def test_persist_recovery_state_survives_reload(tmp_path: Path) -> None:
    journal = RunJournal(storage_path=tmp_path / "run-journal.json")
    mgr = RecoveryManager(journal=journal)
    journal.append(run_id="r20", task_name="t20", status="failed", error="HTTP 500")
    mgr.mark_recovering("r20")
    journal2 = RunJournal(storage_path=tmp_path / "run-journal.json")
    mgr2 = RecoveryManager(journal=journal2)
    runs = mgr2.list_recoverable()
    assert len(runs) == 1
    assert runs[0].retry_count == 1
    assert runs[0].recovery_status == RecoveryStatus.RECOVERING
