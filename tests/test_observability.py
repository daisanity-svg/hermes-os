"""Observability tests."""

from __future__ import annotations

from hermes_os.observability import ObservabilityLog


def test_log_entries_are_append_only() -> None:
    log = ObservabilityLog()
    first = log.log("started")
    second = log.log("completed")
    assert log.entries() == [first, second]
