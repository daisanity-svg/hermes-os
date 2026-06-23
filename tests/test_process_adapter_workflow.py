"""Process adapter workflow tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter
from hermes_os.workflow_records import WorkflowRecords


def test_workflow_id_is_stored_on_submit() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "workflow_id": "wf-1", "payload": {}})
    entry = adapter._run_registry["job"]
    assert entry["workflow_id"] == "wf-1"


def test_list_workflows_returns_running_workflows() -> None:
    records = WorkflowRecords()
    adapter = ProcessAdapter(workflow_records=records)
    adapter.submit({"id": "job", "type": "task", "priority": 1, "workflow_id": "wf-1", "payload": {}})
    records.start("wf-1", "job")
    workflows = adapter.list_workflows()
    assert len(workflows) == 1
    assert workflows[0]["workflow_id"] == "wf-1"
    assert workflows[0]["status"] == "running"


def test_step_id_is_stored_on_submit() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "workflow_id": "wf-1", "step_id": "step-1", "payload": {}})
    entry = adapter._run_registry["job"]
    assert entry.get("step_id") == "step-1"
