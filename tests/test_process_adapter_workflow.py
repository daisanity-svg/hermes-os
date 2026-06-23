"""Process adapter workflow tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_workflow_id_is_stored() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "workflow_id": "wf-1", "payload": {}})
    entry = adapter._run_registry["job"]
    assert entry["workflow_id"] == "wf-1"


def test_workflow_records_start_and_complete() -> None:
    from hermes_os.workflow_records import WorkflowRecords

    records = WorkflowRecords()
    record = records.start("wf-1", "job")
    assert record.status == "running"
    updated = records.complete("wf-1")
    assert updated.status == "completed"
