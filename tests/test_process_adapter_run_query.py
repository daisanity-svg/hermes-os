"""Process adapter run query tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_list_for_run_returns_items_for_run() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    adapter.submit({"id": "job-2", "type": "task", "priority": 2, "run_id": "run-2", "payload": {}})
    result = adapter.list_for_run("run-1")
    assert result["run_id"] == "run-1"
    assert len(result["items"]) == 1
    assert result["items"][0]["run_id"] == "run-1"


def test_list_for_run_returns_metadata() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    adapter.submit({"id": "job-2", "type": "task", "priority": 2, "run_id": "run-1", "payload": {}})
    result = adapter.list_for_run("run-1")
    assert result["metadata"]["item_count"] == 2
    assert result["metadata"]["statuses"]["queued"] == 2


def test_list_for_run_returns_empty_for_unknown_run() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    result = adapter.list_for_run("missing")
    assert result["items"] == []
    assert result["metadata"]["item_count"] == 0


def test_update_run_status_updates_items() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    result = adapter.update_run_status("run-1", "running")
    assert result["status"] == "running"
    assert adapter._run_registry["job"]["status"] == "running"
