"""Process adapter on_complete tests."""

from __future__ import annotations

from hermes_os.process_adapter import ProcessAdapter


def test_on_complete_hook_is_called() -> None:
    calls: list = []

    def on_complete(adapter, item_id, entry, **kwargs):
        calls.append({"adapter": adapter, "item_id": item_id, "entry": entry})

    adapter = ProcessAdapter(on_complete=on_complete)
    adapter.submit({"id": "job", "type": "task", "priority": 1, "payload": {}})
    adapter.complete("job")
    assert len(calls) == 1
    assert calls[0]["item_id"] == "job"
