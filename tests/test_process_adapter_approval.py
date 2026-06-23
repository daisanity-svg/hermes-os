"""Approval tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter
from hermes_os.approval_records import ApprovalRecords


def test_approval_status_is_stored_on_submit() -> None:
    adapter = ProcessAdapter()
    adapter.submit({"id": "job", "type": "task", "priority": 1, "approval_status": "pending", "payload": {}})
    entry = adapter._run_registry["job"]
    assert entry["approval_status"] == "pending"


def test_approve_returns_approved() -> None:
    records = ApprovalRecords()
    records.start("job")
    adapter = ProcessAdapter(approval_records=records)
    result = adapter.approve("job")
    assert result["approval_status"] == "approved"
    assert adapter._run_registry["job"]["approval_status"] == "approved"


def test_reject_returns_rejected() -> None:
    records = ApprovalRecords()
    records.start("job")
    adapter = ProcessAdapter(approval_records=records)
    result = adapter.reject("job")
    assert result["approval_status"] == "rejected"
    assert adapter._run_registry["job"]["approval_status"] == "rejected"
