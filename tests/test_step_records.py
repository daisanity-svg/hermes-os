"""Step records tests."""

from __future__ import annotations

import time

from hermes_os.step_records import StepRecords


def test_step_start_and_get() -> None:
    records = StepRecords()
    record = records.start("step-1", "wf-1", metadata={"label": "alpha"})
    assert record.status == "running"
    assert record.workflow_id == "wf-1"
    fetched = records.get("step-1")
    assert fetched == record


def test_list_for_workflow_filters_running() -> None:
    records = StepRecords()
    records.start("step-1", "wf-1")
    records.start("step-2", "wf-1")
    records.start("step-3", "wf-2")
    items = records.list_for_workflow("wf-1")
    assert [step.step_id for step in items] == ["step-1", "step-2"]
