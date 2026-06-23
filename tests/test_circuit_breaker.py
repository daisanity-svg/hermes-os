"""Circuit breaker tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_circuit_opens_after_threshold_failures() -> None:
    adapter = ProcessAdapter(circuit_failure_threshold=2, circuit_recovery_seconds=1)
    item = adapter.submit({"id": "job-1", "type": "task", "priority": 1, "payload": {}})
    adapter.record_failure(item["workforce_item_id"], error="e1", retry=False)
    adapter.record_failure(item["workforce_item_id"], error="e2", retry=False)
    entry = adapter._run_registry[item["workforce_item_id"]]
    assert entry.get("circuit_open") is True
