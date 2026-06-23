"""Process adapter SLA tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from hermes_os.process_adapter import ProcessAdapter


def test_overdue_task_is_marked_sla_exceeded() -> None:
    adapter = ProcessAdapter(sla_seconds=60)
    adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}})
    adapter.drain(limit=1)
    entry = adapter._run_registry["job-1"]
    now = datetime.utcnow()
    start = now - timedelta(seconds=120)
    entry["started_at"] = start.isoformat()
    adapter._check_sla("job-1")
    assert adapter._run_registry["job-1"]["sla_exceeded"] is True
