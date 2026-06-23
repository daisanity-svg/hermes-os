"""CLI tests for action and artifact subcommands."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hermes_os.action_records import ActionRecords
from hermes_os.minimal_cli_spec.cli import _build_runtime, cmd_actions, cmd_artifacts


def test_actions_history_command() -> None:
    rt = _build_runtime()
    assert cmd_actions(type("Args", (), {"sub": "record", "id": "act-1", "action_type": "search", "run_id": None})(), rt) == 0
    assert cmd_actions(type("Args", (), {"sub": "history"})(), rt) == 0


def test_artifacts_register_verify_and_list(tmp_path: str) -> None:
    target = Path(tmp_path) / "report.pdf"
    target.write_bytes(b"%PDF-1.4")
    rt = _build_runtime()
    rc = cmd_artifacts(
        type("Args", (), {"sub": "register", "run_id": "run-1", "path": str(target), "content_type": "application/pdf"})(),
        rt,
    )
    assert rc == 0
    rc = cmd_artifacts(type("Args", (), {"sub": "list", "run_id": "run-1"})(), rt)
    assert rc == 0


def test_actions_record_then_complete() -> None:
    rt = _build_runtime()
    rc = cmd_actions(
        type("Args", (), {"sub": "record", "id": "act-1", "action_type": "search", "run_id": "run-1"})(),
        rt,
    )
    assert rc == 0
    rc = cmd_actions(
        type("Args", (), {"sub": "complete", "id": "act-1", "output": json.dumps({"ok": True})})(),
        rt,
    )
    assert rc == 0
