"""Process adapter priority inheritance tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_child_inherits_parent_priority() -> None:
    adapter = ProcessAdapter()
    parent = adapter.submit({"id": "parent", "type": "task", "priority": 5, "payload": {}})
    child = adapter.submit({"id": "child", "type": "task", "parent_id": "parent", "payload": {}})
    assert child["priority"] == 5


def test_child_explicit_priority_overrides_parent() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "parent", "type": "task", "priority": 5, "payload": {}})
    child = adapter.submit({"id": "child", "type": "task", "parent_id": "parent", "priority": 2, "payload": {}})
    assert child["priority"] == 2
