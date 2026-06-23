"""Process adapter group tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_group_id_is_stored() -> None:
    adapter = ProcessAdapter()
    result = adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}, "group_id": "alpha"})
    assert result["group_id"] == "alpha"


def test_list_by_group_returns_items() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}, "group_id": "alpha"})
    adapter.submit({"id": "job-2", "type": "task", "priority": 2, "payload": {}, "group_id": "beta"})
    by_group = adapter.list_by_group("alpha")
    assert len(by_group["items"]) == 1
    assert by_group["items"][0]["group_id"] == "alpha"
