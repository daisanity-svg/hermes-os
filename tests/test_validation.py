"""Validation and governance API tests — pydantic removed, use dataclass contracts."""

from __future__ import annotations

import pytest

from hermes_os.action_records import ActionRecords
from hermes_os.lifecycle_records import LifecycleRecords
from hermes_os.ownership_records import OwnershipRecords
from hermes_os.types import ActionStatus, LifecycleEvent


def test_action_records_validation_guard() -> None:
    store = ActionRecords()
    record = store.create("act_1", action_type="search", run_id="run_1")
    assert record.status is ActionStatus.PENDING

    started = store.start("act_1")
    assert started.status is ActionStatus.RUNNING

    done = store.complete("act_1", output_snapshot={"count": 5})
    assert done.status is ActionStatus.COMPLETED

    failed = store.fail("act_1", error="timeout")
    assert failed.status is ActionStatus.FAILED
    assert failed.error == "timeout"


def test_lifecycle_records_validation_guard() -> None:
    log = LifecycleRecords()
    e1 = log.record_transition("run_1", to_status="running", actor="system")
    assert e1.from_status is None
    assert e1.to_status == "running"

    e2 = log.record_transition("run_1", to_status="completed", from_status="running", actor="runner")
    history = log.history_for("run_1")
    assert len(history) == 2
    assert history[-1].to_status == "completed"
    assert history[-1].actor == "runner"
    assert log.current_status("run_1") == "completed"


def test_ownership_records_validation_guard() -> None:
    ledger = OwnershipRecords()
    record = ledger.grant(subject_id="run_1", owner="user:1", source="api")
    assert record.subject_id == "run_1"
    assert ledger.current_owner("run_1") == "user:1"
    assert ledger.get_for_subject("run_1") == [record]
