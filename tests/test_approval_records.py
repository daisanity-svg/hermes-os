"""Approval records tests."""

from __future__ import annotations

import time

from hermes_os.approval_records import ApprovalRecords


def test_approval_start_get() -> None:
    records = ApprovalRecords()
    record = records.start("job-1", metadata={"note": "first"})
    assert record.status == "pending"
    assert record.item_id == "job-1"
    assert records.get("job-1") == record


def test_approve_changes_status() -> None:
    records = ApprovalRecords()
    records.start("job-1")
    updated = records.approve("job-1")
    assert updated.status == "approved"
    assert records.get("job-1").status == "approved"


def test_reject_changes_status() -> None:
    records = ApprovalRecords()
    records.start("job-1")
    updated = records.reject("job-1")
    assert updated.status == "rejected"
    assert records.get("job-1").status == "rejected"


def test_list_pending_filters() -> None:
    records = ApprovalRecords()
    records.start("job-1")
    records.start("job-2")
    records.approve("job-1")
    pending = records.list_pending()
    assert [record.item_id for record in pending] == ["job-2"]
