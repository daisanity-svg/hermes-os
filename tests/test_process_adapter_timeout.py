"""Process adapter timeout tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from hermes_os.process_adapter import ProcessAdapter


def test_execution_timeout_marks_item_failed() -> None:
    adapter = ProcessAdapter(execution_timeout_seconds=0.1)
    item = adapter.submit({"id": "slow-1", "type": "task", "priority": 1, "payload": {"started_at": (datetime.utcnow() - timedelta(seconds=1)).isoformat()}})
    entry = adapter._run_registry[item["workforce_item_id"]]
    entry["started_at"] = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
    adapter.drain(limit=1)
    assert entry["status"] == "failed"
    assert entry["error"] == "execution_timeout"


def test_no_timeout_leaves_completed_runs() -> None:
    adapter = ProcessAdapter()
    item = adapter.submit({"id": "job-ok", "type": "task", "priority": 1, "payload": {}})
    adapter.drain(limit=1)
    entry = adapter._run_registry[item["workforce_item_id"]]
    assert entry["status"] == "completed"
