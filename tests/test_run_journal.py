"""tests for Persistent Run Journal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermes_os.run_journal import RunJournal
from hermes_os.types import RunJournalEntry

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PATH = REPO / "docs" / "sso" / "run-journal.json"


def _make_journal(tmp_path: Path) -> RunJournal:
    target = tmp_path / "run-journal.json"
    return RunJournal(storage_path=target)


def test_append_creates_entry(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    entry = journal.append(
        run_id="run-001",
        task_name="sprint planning",
        project_code="hermes-os",
        project_name="Hermes OS",
        status="running",
        last_event="started",
        next_action="continue execution",
    )
    assert entry.run_id == "run-001"
    assert entry.task_name == "sprint planning"
    assert entry.status == "running"
    assert entry.project_code == "hermes-os"
    assert entry.project_name == "Hermes OS"
    assert entry.last_event == "started"
    assert entry.next_action == "continue execution"
    assert tmp_path.joinpath("run-journal.json").exists()


def test_append_twice_is_idempotent_update(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    journal.append(run_id="run-002", task_name="task-a", status="queued")
    updated = journal.append(
        run_id="run-002",
        task_name="task-a",
        status="completed",
        last_event="done",
    )
    assert updated.status == "completed"
    assert updated.last_event == "done"
    assert updated.created_at != updated.updated_at


def test_update_modifies_fields(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    journal.append(run_id="run-003", task_name="task-b", status="running")
    result = journal.update(
        "run-003",
        status="failed",
        error="connection timeout",
        next_action="retry",
    )
    assert result is not None
    assert result.status == "failed"
    assert result.error == "connection timeout"
    assert result.next_action == "retry"


def test_update_missing_run_returns_none(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    assert journal.update("ghost-run", status="done") is None


def test_list_returns_entries(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    journal.append(run_id="run-a", task_name="a", project_code="P1", status="done")
    journal.append(run_id="run-b", task_name="b", project_code="P2", status="running")
    journal.append(run_id="run-c", task_name="c", project_code="P1", status="running")

    all_entries = journal.list()
    assert len(all_entries) == 3

    p1_entries = journal.list(project_code="P1")
    assert len(p1_entries) == 2
    assert all(e.project_code == "P1" for e in p1_entries)

    running_entries = journal.list(status="running")
    assert len(running_entries) == 2


def test_list_limit(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    for i in range(5):
        journal.append(run_id=f"run-{i}", task_name=f"t-{i}", status="done")
    limited = journal.list(limit=2)
    assert len(limited) == 2


def test_get_returns_single_entry(tmp_path: Path) -> None:
    journal = _make_journal(tmp_path)
    journal.append(run_id="run-get", task_name="target", status="queued")
    entry = journal.get("run-get")
    assert entry is not None
    assert entry.task_name == "target"
    assert journal.get("ghost") is None


def test_persist_survives_reload(tmp_path: Path) -> None:
    target = tmp_path / "run-journal.json"
    journal1 = RunJournal(storage_path=target)
    journal1.append(
        run_id="run-persist",
        task_name="persist-test",
        project_code="X",
        project_name="X Project",
        status="completed",
        error=None,
        next_action="none",
    )
    journal2 = RunJournal(storage_path=target)
    entry = journal2.get("run-persist")
    assert entry is not None
    assert entry.project_name == "X Project"
    assert entry.status == "completed"
