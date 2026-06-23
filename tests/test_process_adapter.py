"""Process adapter tests."""

from __future__ import annotations

import pytest

from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.process_adapter import ProcessAdapter


def test_drain_empty_returns_empty_list() -> None:
    adapter = ProcessAdapter()
    assert adapter.drain(limit=5) == []


def test_complete_updates_status() -> None:
    adapter = ProcessAdapter()
    item = adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}})
    assert item["status"] == "queued"
    completed = adapter.complete(item["workforce_item_id"])
    assert completed["status"] == "completed"


def test_submit_defaults_and_memory() -> None:
    adapter = ProcessAdapter()
    item = adapter.submit({"id": "job-1"})
    assert item["status"] == "queued"
    assert item["workforce_item_id"] == "job-1"


def test_batch_submit_queues_multiple() -> None:
    adapter = ProcessAdapter()
    items = adapter.batch_submit([
        {"id": "job-1", "type": "task", "priority": 1, "payload": {}},
        {"id": "job-2", "type": "task", "priority": 2, "payload": {}},
    ])
    assert len(items) == 2
