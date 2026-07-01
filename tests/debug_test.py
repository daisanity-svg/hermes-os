"""Debug test for continuous loop."""
from __future__ import annotations

from typing import Any, Dict
from pathlib import Path

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
    def _make(adapter: MockAdapter, **kwargs: Any) -> ContinuousDevelopmentLoop:
        journal_path = kwargs.pop("storage_path", tmp_path / "journal.json")
        return ContinuousDevelopmentLoop(
            adapter,
            storage_path=journal_path,
            **kwargs,
        )
    return _make


class TestDebug:
    def test_single_step_executes_task(self, loop_factory, mock_adapter: MockAdapter) -> None:
        scheduler = AutoScheduler()
        scheduler.reload()
        scheduler._candidates["task-1"] = TaskCandidate(
            item_id="task-1",
            title="實作測試任務",
            priority=TaskPriority.P2,
            source=SchedulerSource.RUNS,
            status=TaskStatus.QUEUED,
            auto_start=True,
        )
        scheduler._enforce_guardrails()
        scheduler.reload = lambda *a, **k: None

        loop = loop_factory(mock_adapter, scheduler=scheduler)
        status = loop.step()

        print("STEP STATUS:", status["last_step"]["status"])
        print("COMPLETED:", status["completed_count"])
        print("ADAPTER SUBMITTED:", mock_adapter._submitted)
        print("ADAPTER COMPLETED:", mock_adapter._completed)
        assert status["state"] == LoopState.IDLE.value
        assert status["completed_count"] == 1
        assert status["last_step"]["status"] == "completed"
        assert status["last_step"]["task_item_id"] == "task-1"
