"""Run params records tests."""

from __future__ import annotations

import time

from hermes_os.run_params_records import RunParamsRecords


def test_set_and_get_params() -> None:
    records = RunParamsRecords()
    record = records.set("run-1", {"key": "value"})
    assert record.run_id == "run-1"
    assert record.params["key"] == "value"
    assert records.get("run-1") is record


def test_update_params() -> None:
    records = RunParamsRecords()
    first = records.set("run-1", {"key": "v1"})
    second = records.set("run-1", {"key": "v2"})
    assert first is second
    assert second.params["key"] == "v2"
    assert second.updated_at >= first.created_at


def test_list_for_run_returns_empty_for_missing() -> None:
    records = RunParamsRecords()
    assert records.list_for_run("missing") == {"run_id": "missing", "params": {}}
