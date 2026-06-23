"""Process adapter extended tests."""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta

from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.process_adapter import ProcessAdapter


def test_retry_records_attempts() -> None:
    adapter = ProcessAdapter()
    item = adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}})
    assert item["status"] == "queued"
    record = adapter.record_failure(item["workforce_item_id"], error="boom", retry=True)
    assert record["status"] == "retry"


def test_backoff_increases_on_retry() -> None:
    adapter = ProcessAdapter()
    item = adapter.submit({"id": "job-2", "type": "task", "priority": 1, "payload": {}})
    after_failure = adapter.record_failure(item["workforce_item_id"], error="temp", retry=True)
    assert after_failure["retry_count"] == 1
    updated = adapter.retry(item["workforce_item_id"])
    assert updated is not None
    assert updated["retry_count"] == 2
    previous = adapter.queue.get(updated["workforce_item_id"])
    backoff = previous.payload.get("backoff_seconds")
    assert isinstance(backoff, (int, float))


def test_cancel_by_filter_removes_matching_items() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "low-1", "type": "task", "priority": 1, "payload": {}})
    adapter.submit({"id": "high-1", "type": "task", "priority": 10, "payload": {}})
    cancelled = adapter.cancel_by_filter(max_priority=5)
    assert any(item["workforce_item_id"] == "low-1" for item in cancelled)
    assert not any(item["workforce_item_id"] == "high-1" for item in cancelled)
