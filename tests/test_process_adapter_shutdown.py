"""Process adapter shutdown and circuit breaker tests."""

from __future__ import annotations

import pytest

from hermes_os.process_adapter import ProcessAdapter


def test_shutdown_drains_queued_items() -> None:
    adapter = ProcessAdapter(drain_timeout_seconds=1)
    adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}})
    outcome = adapter.shutdown()
    assert outcome["status"] == "shutdown"
    assert outcome["drained_count"] >= 1


def test_graceful_shutdown_blocks_new_submissions() -> None:
    adapter = ProcessAdapter()
    adapter.request_shutdown()
    with pytest.raises(Exception):
        adapter.submit({"id": "job-2", "type": "task", "priority": 1, "payload": {}})
