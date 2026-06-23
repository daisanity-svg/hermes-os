"""Process adapter tests."""

from __future__ import annotations

import pytest

from hermes_os.process_adapter import ProcessAdapter


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
