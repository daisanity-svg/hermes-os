"""Action records extended tests."""

from __future__ import annotations

import pytest

from hermes_os.action_records import ActionRecords
from hermes_os.types import ActionStatus


def test_complete_returns_none_for_missing_action() -> None:
    store = ActionRecords()
    assert store.complete("missing") is None


def test_fail_returns_none_for_missing_action() -> None:
    store = ActionRecords()
    assert store.fail("missing") is None


def test_history_limits_results() -> None:
    store = ActionRecords()
    for idx in range(5):
        store.create(f"act_{idx}", "task.run")
    assert len(store.history()) == 5
    assert len(store.history(limit=2)) == 2


def test_create_duplicate_action_raises() -> None:
    store = ActionRecords()
    store.create("act_1", "task.run")
    with pytest.raises(ValueError):
        store.create("act_1", "task.run")
