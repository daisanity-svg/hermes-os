"""Retry hook tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_custom_retry_hook_is_called() -> None:
    calls: list = []

    def hook(adapter, item_id, entry, **kwargs):
        calls.append((item_id, entry.get("retry_count")))

    adapter = ProcessAdapter(retry_hook=hook)
    adapter.submit({"id": "job", "type": "task", "priority": 1, "payload": {}})
    adapter.record_failure("job", error="boom", retry=True)
    assert len(calls) == 1
    assert calls[0][0] == "job"
