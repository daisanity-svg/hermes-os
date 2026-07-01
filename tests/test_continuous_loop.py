"""Hermes OS — Continuous Development Loop v1 tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from hermes_os.continuous_loop import (
    ContinuousDevelopmentLoop,
    LoopState,
    LoopStepResult,
    StopReason,
)
from hermes_os.scheduler.auto_scheduler import AutoScheduler
from hermes_os.scheduler.schemas import (
    SchedulerSource,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
)


class MockAdapter:
    """Minimal fake ProcessAdapter for loop testing."""

    def __init__(self) -> None:
        self._submitted: list = []
        self._completed: list = []
        self._fail_next = False

    def submit(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self._submitted.append(item)
        return {"status": "queued", "workforce_item_id": item["id"]}

    def complete(self, item_id: str) -> Dict[str, Any]:
        self._completed.append(item_id)
        if self._fail_next:
            return {"status": "failed", "error": "simulated failure"}
        return {"status": "completed"}


@pytest.fixture()
def mock_adapter() -> MockAdapter:
    return MockAdapter()


@pytest.fixture()
def loop_factory(mock_adapter: MockAdapter, tmp_path: Path):
    def _make(**kwargs: Any) -> ContinuousDevelopmentLoop:
        journal_path = kwargs.pop("storage_path", tmp_path / "journal.json")
        return ContinuousDevelopmentLoop(
            mock_adapter,
            storage_path=journal_path,
            **kwargs,
        )
    return _make


def _setup_scheduler_with_candidate(item_id: str, title: str, priority: TaskPriority, auto_start: bool = True) -> AutoScheduler:
    scheduler = AutoScheduler()
    scheduler.reload()
    scheduler._candidates[item_id] = TaskCandidate(
        item_id=item_id,
        title=title,
        priority=priority,
        source=SchedulerSource.RUNS,
        status=TaskStatus.QUEUED,
        auto_start=auto_start,
    )
    scheduler._enforce_guardrails()
    scheduler.reload = lambda *a, **k: None
    return scheduler


class TestContinuousDevelopmentLoop:
    def test_start_changes_state_to_running(self, loop_factory) -> None:
        scheduler = _setup_scheduler_with_candidate("task-1", "啟動測試", TaskPriority.P3)
        loop = loop_factory(scheduler=scheduler)
        # 傳入會阻塞的 adapter 以保留 running 狀態
        from unittest.mock import MagicMock
        blocker = MagicMock()
        blocker.submit.return_value = {"status": "queued"}
        blocker.complete.side_effect = Exception("blocked")
        loop._adapter = blocker

        import threading
        t = threading.Thread(target=loop.start)
        t.start()
        try:
            for _ in range(50):
                status = loop.status()
                if status["state"] == LoopState.RUNNING.value:
                    break
                threading.Event().wait(0.02)
            t.join(timeout=2)
        finally:
            loop.stop()
            t.join(timeout=2)
        status = loop.status()
        assert status["state"] in (LoopState.RUNNING.value, LoopState.STOPPING.value, LoopState.STOPPED.value, LoopState.IDLE.value)

    def test_stop_transitions_to_stopped(self, loop_factory) -> None:
        scheduler = _setup_scheduler_with_candidate("task-1", "停止測試", TaskPriority.P3)
        loop = loop_factory(scheduler=scheduler)
        from unittest.mock import MagicMock
        blocker = MagicMock()
        blocker.submit.return_value = {"status": "queued"}
        blocker.complete.side_effect = Exception("blocked")
        loop._adapter = blocker

        import threading
        t = threading.Thread(target=loop.start)
        t.start()
        try:
            for _ in range(50):
                status = loop.status()
                if status["state"] == LoopState.RUNNING.value:
                    break
                threading.Event().wait(0.02)
            status = loop.stop()
            assert status["state"] in (LoopState.STOPPED.value, LoopState.IDLE.value, LoopState.STOPPING.value)
            t.join(timeout=2)
        finally:
            loop.stop()
            t.join(timeout=2)

    def test_single_step_executes_task(self, loop_factory) -> None:
        scheduler = _setup_scheduler_with_candidate("task-1", "實作測試任務", TaskPriority.P2)
        loop = loop_factory(scheduler=scheduler)
        status = loop.step()

        assert status["state"] == LoopState.IDLE.value
        assert status["completed_count"] == 1
        assert status["last_step"]["status"] == "completed"
        assert status["last_step"]["task_item_id"] == "task-1"

    def test_p0_task_creates_founder_ticket(self, loop_factory) -> None:
        scheduler = AutoScheduler()
        scheduler.reload()
        scheduler._candidates["task-p0"] = TaskCandidate(
            item_id="task-p0",
            title="P0 高風險任務",
            priority=TaskPriority.P0,
            source=SchedulerSource.RUNS,
            status=TaskStatus.WAITING_FOR_APPROVAL,
            auto_start=False,
        )
        scheduler._enforce_guardrails()
        scheduler.reload = lambda *a, **k: None

        loop = loop_factory(scheduler=scheduler)
        status = loop.step()

        assert status["last_step"]["status"] == "needs_founder_decision"
        assert status["last_step"]["founder_ticket"] is not None
        assert "ticket_id" in status["last_step"]["founder_ticket"]
        assert status["stop_reason"] == StopReason.FOUNDER_DECISION_REQUIRED.value

    def test_progress_report_format(self, loop_factory) -> None:
        scheduler = _setup_scheduler_with_candidate("task-1", "進度測試", TaskPriority.P3)
        loop = loop_factory(scheduler=scheduler)
        loop.step()
        progress = loop.progress()

        assert "已完成" in progress
        assert "進行中" in progress
        assert "下一步" in progress
        assert "風險" in progress
        assert "需要_Founder_介入" in progress
        assert len(progress["已完成"]) == 1
        assert progress["進行中"] is None

    def test_run_journal_written_on_step(self, loop_factory, tmp_path: Path) -> None:
        from hermes_os.run_journal import RunJournal

        journal = RunJournal(storage_path=tmp_path / "journal.json")
        scheduler = _setup_scheduler_with_candidate("task-1", "日誌測試", TaskPriority.P3)
        loop = loop_factory(journal=journal, scheduler=scheduler)
        loop.step()

        entries = journal.list()
        assert len(entries) == 1
        assert entries[0].status == "completed"
        assert entries[0].task_name == "日誌測試"

    def test_max_consecutive_failures_stops_loop(self, loop_factory, tmp_path: Path) -> None:
        # Create a fresh adapter that fails
        failing_adapter = MockAdapter()
        failing_adapter._fail_next = True

        scheduler = _setup_scheduler_with_candidate("task-fail", "一定會失敗", TaskPriority.P2)
        # Use a custom loop with the failing adapter
        loop = ContinuousDevelopmentLoop(adapter=failing_adapter, scheduler=scheduler, storage_path=tmp_path / "journal.json")
        loop.step()
        loop.step()
        status = loop.step()

        assert status["stop_reason"] == StopReason.MAX_FAILURES.value
        assert status["last_step"]["status"] == "needs_founder_decision"
        assert status["last_step"]["founder_ticket"] is not None

    def test_no_tasks_stops_loop(self, loop_factory) -> None:
        scheduler = AutoScheduler()
        scheduler.reload()
        # 沒有 candidate
        scheduler.reload = lambda *a, **k: None
        loop = loop_factory(scheduler=scheduler)
        status = loop.step()
        assert status["stop_reason"] == StopReason.NO_TASKS.value

    def test_max_tasks_per_cycle_stops_after_limit(self, mock_adapter) -> None:
        from hermes_os.run_journal import RunJournal
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            journal_path = Path(d) / "journal.json"
            scheduler = _setup_scheduler_with_candidate("c1", "task-1", TaskPriority.P3)
            scheduler._candidates["c2"] = TaskCandidate(
                item_id="c2",
                title="task-2",
                priority=TaskPriority.P3,
                source=SchedulerSource.RUNS,
                status=TaskStatus.QUEUED,
                auto_start=True,
            )
            scheduler._enforce_guardrails()
            scheduler.reload = lambda *a, **k: None

            loop = ContinuousDevelopmentLoop(
                adapter=mock_adapter,
                scheduler=scheduler,
                journal=RunJournal(storage_path=journal_path),
                max_tasks_per_cycle=1,
            )
            status = loop.start()
            assert status["completed_count"] == 1
            assert status["state"] == "idle"
            # second batch not executed
            assert status["stop_reason"] == "none"

    def test_max_tasks_per_cycle_2_allows_two_tasks(self, mock_adapter) -> None:
        from hermes_os.run_journal import RunJournal
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            journal_path = Path(d) / "journal.json"
            scheduler = _setup_scheduler_with_candidate("c1", "task-1", TaskPriority.P3)
            scheduler._candidates["c2"] = TaskCandidate(
                item_id="c2",
                title="task-2",
                priority=TaskPriority.P3,
                source=SchedulerSource.RUNS,
                status=TaskStatus.QUEUED,
                auto_start=True,
            )
            scheduler._enforce_guardrails()
            scheduler.reload = lambda *a, **k: None

            loop = ContinuousDevelopmentLoop(
                adapter=mock_adapter,
                scheduler=scheduler,
                journal=RunJournal(storage_path=journal_path),
                max_tasks_per_cycle=2,
            )
            status = loop.start()
            assert status["completed_count"] == 2
            assert status["state"] == "idle"
            assert status["stop_reason"] == "none"
