"""Hermes OS Watchdog — MVP 單元測試。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest

from hermes_os.watchdog.detector import STAGNATION_RULES, StagnationDetector, stagnation_score
from hermes_os.watchdog.executor import ActionExecutor
from hermes_os.watchdog.schemas import AuditRecord, TaskState, TaskStatus, WatchdogDecision
from hermes_os.watchdog.storage import WatchdogStorage
from hermes_os.watchdog.supervisor import GPTDecisionCore


# === fixtures ===


@pytest.fixture()
def _storage(tmp_path: Path) -> WatchdogStorage:
    return WatchdogStorage(db_path=tmp_path / "watchdog.db")


@pytest.fixture()
def sample_state() -> TaskState:
    now = datetime.utcnow()
    return TaskState(
        task_id="task-1",
        project="demo",
        status=TaskStatus.IN_PROGRESS,
        last_activity_ts=now - timedelta(minutes=20),
        last_user_reply_ts=now - timedelta(minutes=30),
        consecutive_idle_checks=1,
        error_summary=None,
        blockers=[],
        current_action="running test",
        owner="alice",
    )


# === TaskState / WatchdogDecision schema ===


class TestSchemas:
    def test_task_state_serialize_roundtrip(self, sample_state: TaskState) -> None:
        dumped = sample_state.model_dump_json()
        restored = TaskState.model_validate_json(dumped)
        assert restored.task_id == "task-1"
        assert restored.status == TaskStatus.IN_PROGRESS

    def test_task_state_status_enum(self) -> None:
        state = TaskState(
            task_id="t",
            project="p",
            status=TaskStatus.FAILED,
            last_activity_ts=datetime.utcnow(),
        )
        assert state.status == "failed"

    def test_watchdog_decision_defaults(self) -> None:
        decision = WatchdogDecision(
            task_id="t",
            decision="escalate",
            reason="卡住",
            action_plan=["通知"],
            risk="無",
        )
        assert decision.requires_human is False
        assert decision.next_check is None

    def test_audit_record_roundtrip(self, sample_state: TaskState) -> None:
        decision = WatchdogDecision(
            task_id=sample_state.task_id,
            decision="proceed",
            reason="ok",
            action_plan=[],
            risk="low",
        )
        record = AuditRecord(
            ts=datetime.utcnow(),
            task_id=sample_state.task_id,
            trigger="gpt_decision",
            state_snapshot=sample_state,
            decision=decision,
            result="success",
        )
        json_text = record.model_dump_json()
        restored = AuditRecord.model_validate_json(json_text)
        assert restored.trigger == "gpt_decision"
        assert restored.decision.decision == "proceed"


# === StagnationDetector ===


class TestStagnationDetector:
    def now(self, minutes_ago: int = 0) -> datetime:
        return datetime.utcnow() - timedelta(minutes=minutes_ago)

    def test_idle_not_stagnant_below_threshold(self) -> None:
        state = TaskState(
            task_id="t",
            project="p",
            status=TaskStatus.IN_PROGRESS,
            last_activity_ts=self.now(minutes_ago=10),
            consecutive_idle_checks=0,
        )
        det = StagnationDetector()
        assert det.scan([state], self.now()) == []

    def test_idle_stagnant_after_threshold(self) -> None:
        state = TaskState(
            task_id="t",
            project="p",
            status=TaskStatus.IN_PROGRESS,
            last_activity_ts=self.now(minutes_ago=16),
            consecutive_idle_checks=0,
        )
        det = StagnationDetector()
        result = det.scan([state], self.now())
        assert len(result) == 1
        assert result[0].consecutive_idle_checks == 1

    def test_completed_never_stagnant(self) -> None:
        state = TaskState(
            task_id="t",
            project="p",
            status=TaskStatus.COMPLETED,
            last_activity_ts=self.now(minutes_ago=120),
            consecutive_idle_checks=0,
        )
        det = StagnationDetector()
        assert det.scan([state], self.now()) == []

    def test_score_threshold(self) -> None:
        state = TaskState(
            task_id="t",
            project="p",
            status=TaskStatus.IN_PROGRESS,
            last_activity_ts=self.now(minutes_ago=20),
            last_user_reply_ts=self.now(minutes_ago=26),
            consecutive_idle_checks=3,
        )
        # 20min -> rule A +1, 26min -> rule B wait user_reply_idle_minutes is 25 so +1
        # consecutive_idle_checks >= 3 -> +2
        # total should >= 2
        assert stagnation_score(state, self.now()) >= 2


# === Storage ===


class TestStorage:
    def test_upsert_and_get(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        _storage.upsert_task_state(sample_state)
        loaded = _storage.get_task_state("task-1")
        assert loaded is not None
        assert loaded.project == "demo"
        assert loaded.status == TaskStatus.IN_PROGRESS

    def test_upsert_overwrite(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        _storage.upsert_task_state(sample_state)
        updated = TaskState(
            task_id="task-1",
            project="demo",
            status=TaskStatus.FAILED,
            last_activity_ts=datetime.utcnow(),
            consecutive_idle_checks=2,
        )
        _storage.upsert_task_state(updated)
        loaded = _storage.get_task_state("task-1")
        assert loaded is not None
        assert loaded.status == TaskStatus.FAILED
        assert loaded.consecutive_idle_checks == 2

    def test_add_audit_and_query(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        decision = WatchdogDecision(
            task_id=sample_state.task_id,
            decision="escalate",
            reason="idle",
            action_plan=["alert"],
            risk="none",
        )
        record = AuditRecord(
            ts=datetime.utcnow(),
            task_id=sample_state.task_id,
            trigger="gpt_decision",
            state_snapshot=sample_state,
            decision=decision,
            result="success",
        )
        _storage.add_audit(record)
        records = _storage.list_audit_for_task(sample_state.task_id)
        assert len(records) == 1
        assert records[0].trigger == "gpt_decision"

    def test_recent_audit(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        for i in range(10):
            record = AuditRecord(
                ts=datetime.utcnow(),
                task_id=f"task-{i}",
                trigger="detected",
                state_snapshot=sample_state,
                result="success",
            )
            _storage.add_audit(record)
        recent = _storage.list_recent_audit(limit=5)
        assert len(recent) == 5


# === Executor ===


class TestExecutor:
    def test_validate_action_blocks_forbidden(self) -> None:
        ex = ActionExecutor(None)
        assert ex._validate_action("notify_user") is True
        assert ex._validate_action("delete_files") is False
        assert ex._validate_action("reset && retry") is False
        assert ex._validate_action("truncate logs; drop table") is False

    def test_execute_proceed_records_audit(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        decision = WatchdogDecision(
            task_id=sample_state.task_id,
            decision="proceed",
            reason="ok",
            action_plan=["retry"],
            risk="low",
        )
        ex = ActionExecutor(_storage)
        record = ex.execute(sample_state, decision)
        assert record.result == "success"
        assert record.trigger == "execute"

    def test_execute_escalate_skips_action(self, _storage: WatchdogStorage, sample_state: TaskState) -> None:
        assert _storage is not None
        decision = WatchdogDecision(
            task_id=sample_state.task_id,
            decision="escalate",
            reason="human needed",
            action_plan=[],
            risk="high",
            requires_human=True,
        )
        ex = ActionExecutor(_storage)
        record = ex.execute(sample_state, decision)
        assert record.result == "skipped"
        assert "escalate:escalate" == record.action_taken


# === GPT 核心 — mock smoke test（無真實 LLM 呼叫） ===


class TestGPTDecisionCoreSmoke:
    """mock openai 以防在無網路 / 無 key 的 CI 環境炸掉。"""

    def test_schema_and_prompt_emit_without_client(self, sample_state: TaskState) -> None:
        core = GPTDecisionCore(storage=None)  # type: ignore[arg-type]
        system_msg, user_msg = core._build_messages(sample_state)
        assert "停滯" in system_msg["content"]
        assert str(sample_state.task_id) in user_msg["content"]
