"""Minimal Hermes OS runtime tests."""

from __future__ import annotations

import pytest

from hermes_os.minimal_cli_spec.cli import main


def test_status_command_prints_no_snapshot_yet() -> None:
    rc = main(["status"])
    assert rc == 0


def test_queue_submit_and_drain() -> None:
    rc = main(["queue", "submit", "job-1", "--priority", "2"])
    assert rc == 0
    rc = main(["queue", "drain", "--limit", "1"])
    assert rc == 0


def test_queue_peek_after_submit() -> None:
    rc = main(["queue", "submit", "job-2", "--priority", "3"])
    assert rc == 0
    rc = main(["queue", "peek"])
    assert rc == 0
