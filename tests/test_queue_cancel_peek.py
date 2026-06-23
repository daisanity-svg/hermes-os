"""Workforce queue tests for cancellation and peek behavior."""

from __future__ import annotations

import pytest

from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


def test_peek_returns_highest_priority_without_removal() -> None:
    queue = WorkforceQueue()
    queue.enqueue(WorkforceItem(item_id="low", item_type="task", priority=1))
    queue.enqueue(WorkforceItem(item_id="mid", item_type="task", priority=3))
    queue.enqueue(WorkforceItem(item_id="high", item_type="task", priority=5))

    first = queue.peek()
    assert first.item_id == "high"
    assert len(queue) == 3


def test_cancel_removes_item_and_returns_cancelled_status() -> None:
    queue = WorkforceQueue()
    queue.enqueue(WorkforceItem(item_id="job-1", item_type="task", priority=1))
    cancelled = queue.cancel("job-1")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert queue.get("job-1") is None
    assert len(queue) == 0


def test_cancel_unknown_id_returns_none() -> None:
    queue = WorkforceQueue()
    assert queue.cancel("missing") is None
