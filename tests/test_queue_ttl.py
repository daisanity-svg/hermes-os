"""Workforce queue TTL and priority tests."""

from __future__ import annotations

import time

import pytest

from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


def test_enqueue_with_ttl_removes_expired_items() -> None:
    queue = WorkforceQueue()
    item = WorkforceItem(item_id="task_a", item_type="task", priority=1, payload={})
    queue.enqueue(item, ttl_seconds=1)
    time.sleep(1.1)
    assert queue.peek() is None


def test_set_priority_keeps_same_item() -> None:
    queue = WorkforceQueue()
    item = WorkforceItem(item_id="task_a", item_type="task", priority=1, payload={})
    queue.enqueue(item)
    updated = queue.set_priority("task_a", 10)
    assert updated is not None
    assert updated.priority == 10
    assert queue.get("task_a").priority == 10
