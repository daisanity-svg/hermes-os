"""Action Records tests."""

from __future__ import annotations

import pytest

from hermes_os.action_records import ActionRecords
from hermes_os.types import ActionStatus


def test_record_then_complete_round_trip() -> None:
    log = ActionRecords()
    record = log.create("act-1", "task.run")
    assert record.status == ActionStatus.PENDING
    completed = log.complete("act-1", output_snapshot={"ok": True})
    assert completed is not None
    assert completed.status == ActionStatus.COMPLETED
    assert completed.finished_at is not None


def test_record_duplicate_raises() -> None:
    log = ActionRecords()
    log.create("act-1", "task.run")
    with pytest.raises(ValueError):
        log.create("act-1", "task.run")


def test_history_returns_records() -> None:
    log = ActionRecords()
    log.create("act-1", "task.run")
    log.create("act-2", "task.run")
    assert len(log.history()) == 2


def test_fail_records_error() -> None:
    log = ActionRecords()
    log.create("act-1", "task.run")
    updated = log.fail("act-1", error="boom")
    assert updated.status == ActionStatus.FAILED
    assert updated.error == "boom"
