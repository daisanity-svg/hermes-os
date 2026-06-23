"""Process adapter cancel-by-group tests."""

from __future__ import annotations

import pytest

from hermes_os.process_adapter import ProcessAdapter


def test_cancel_by_group() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "group_id": "alpha", "payload": {}})
    adapter.submit({"id": "job2", "type": "task", "priority": 1, "group_id": "beta", "payload": {}})
    cancelled = adapter.cancel_by_group("alpha")
    assert len(cancelled) == 1


def test_cancel_by_group_empty_when_group_missing() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "payload": {}})
    cancelled = adapter.cancel_by_group("alpha")
    assert cancelled == []
