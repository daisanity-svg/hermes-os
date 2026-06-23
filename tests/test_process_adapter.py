"""Process adapter tests."""

from __future__ import annotations

import pytest

from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.process_adapter import ProcessAdapter
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


def test_submit_queues_workforce_item() -> None:
    adapter = ProcessAdapter()
    result = adapter.submit({"id": "item-1", "type": "task", "priority": 2, "payload": {"cmd": "run"}})
    assert result == {"workforce_item_id": "item-1", "status": "queued"}
    assert len(adapter.queue) == 1


def test_drain_returns_items_by_priority() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "low", "type": "task", "priority": 1})
    adapter.submit({"id": "high", "type": "task", "priority": 9})
    adapter.submit({"id": "mid", "type": "task", "priority": 5})

    first = adapter.drain(1)
    assert len(first) == 1
    assert first[0]["id"] == "high"
    assert len(adapter.queue) == 2


def test_drain_empty_returns_empty_list() -> None:
    adapter = ProcessAdapter()
    assert adapter.drain(1) == []
    assert adapter.memory.count() == 0


def test_complete_updates_status(tmp_path: str) -> None:
    store = WorkforceQueue()
    item = WorkforceItem(item_id="job-1", item_type="task", priority=1)
    store.enqueue(item)
    completed = store.complete("job-1")
    assert completed is not None
    assert completed.status == "completed"
    assert store.get("job-1") is None
    assert len(store) == 0


def test_submit_defaults_and_memory() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "item-1"})
    assert adapter.memory.count() == 1
    last = adapter.submit({"id": "item-2", "type": "analysis", "payload": {"x": 1}})
    assert last["status"] == "queued"
    both = adapter.drain(2)
    assert len(both) == 2
    assert adapter.memory.count() == 3
