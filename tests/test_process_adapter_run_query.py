"""Process adapter run query tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_list_for_run_returns_items_for_run() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    adapter.submit({"id": "job-2", "type": "task", "priority": 2, "run_id": "run-2", "payload": {}})
    items = adapter.list_for_run("run-1")
    assert len(items) == 1
    assert items[0]["run_id"] == "run-1"


def test_list_for_run_returns_empty_for_unknown_run() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "run_id": "run-1", "payload": {}})
    items = adapter.list_for_run("missing")
    assert items == []


def test_list_for_run_returns_empty_when_no_run_id() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "payload": {}})
    items = adapter.list_for_run(None)
    assert items == []
