"""CLI __main__ integration tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hermes_os.minimal_cli_spec.cli import main


def test_main_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_main_status_without_snapshot() -> None:
    assert main(["status"]) == 0


def test_main_actions_record_and_history() -> None:
    assert main(["actions", "record", "main-1", "task.run"]) == 0
    assert main(["actions", "history"]) == 0
