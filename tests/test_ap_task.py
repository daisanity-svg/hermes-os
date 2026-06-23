"""AP Task payload schema tests."""

from __future__ import annotations

import pytest

from hermes_os.ap_task import APTask, TaskStatus, to_ap_task


def test_defaults_apply_when_input_is_minimal() -> None:
    task = to_ap_task({"id": "job-1"})
    assert task.task_id == "job-1"
    assert task.task_type == "task"
    assert task.priority == 0
    assert task.metadata == {}


def test_passthrough_when_input_provides_all_fields() -> None:
    source = {
        "id": "job-1",
        "type": "analysis",
        "priority": 9,
        "payload": {"cmd": "run"},
        "metadata": {"x": 1},
    }
    task = to_ap_task(source)
    assert task.task_type == "analysis"
    assert task.priority == 9
    assert task.payload == {"cmd": "run"}
    assert task.metadata == {"x": 1}


def test_non_string_id_is_accepted_and_preserved() -> None:
    task = APTask(task_id=123)
    assert task.task_id == 123


def test_negative_priority_is_normalized_to_zero() -> None:
    task = to_ap_task({"id": "job-1", "priority": -5})
    assert task.priority == 0


def test_multiple_items_preserve_insertion_time_order() -> None:
    items = [to_ap_task({"id": f"job-{i}", "priority": i}) for i in range(3)]
    assert [i.task_id for i in items] == ["job-0", "job-1", "job-2"]
