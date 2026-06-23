"""MVP skeleton tests — one per module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hermes_os.types import (
    ActionRecord,
    ActionStatus,
    ArtifactRef,
    ControlCenterSnapshot,
    LifecycleEvent,
    MemoryLogEntry,
    OwnershipRecord,
    WorkforceItem,
)
# ---- artifact_registry ----
from hermes_os.artifact_registry import ArtifactRegistry


def test_artifact_registry_round_trip(tmp_path: Path) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path / "art"))
    registry.register("run_1", "report.pdf", b"%PDF-1.4", content_type="application/pdf")
    registry.register("run_1", "summary.txt", b"hello world")
    items = registry.list_for_run("run_1")
    assert {i.filename for i in items} == {"report.pdf", "summary.txt"}
    assert registry.get("run_1::report.pdf").content_type == "application/pdf"
    assert registry.get("run_1::report.pdf").size_bytes == 8
    assert registry.get("run_1::summary.txt").size_bytes == 11
    assert registry.delete("run_1::report.pdf") is True
    assert registry.get("run_1::report.pdf") is None
    remaining = {i.filename for i in registry.list_for_run("run_1")}
    assert remaining == {"summary.txt"}


# ---- ownership_records ----
from hermes_os.ownership_records import OwnershipRecords


def test_ownership_records_grant_and_query() -> None:
    ledger = OwnershipRecords()
    record = ledger.grant(subject_id="run_1", owner="user:1", source="api")
    assert record.subject_id == "run_1"
    assert ledger.current_owner("run_1") == "user:1"
    assert ledger.get_for_subject("run_1") == [record]


# ---- lifecycle_records ----
from hermes_os.lifecycle_records import LifecycleRecords


def test_lifecycle_records_transitions() -> None:
    log = LifecycleRecords()
    e1 = log.record_transition("run_1", to_status="running", actor="system")
    e2 = log.record_transition(
        "run_1", to_status="completed", from_status="running", actor="runner"
    )
    history = log.history_for("run_1")
    assert len(history) == 2
    assert history[-1].to_status == "completed"
    assert history[-1].actor == "runner"
    assert log.current_status("run_1") == "completed"


# ---- action_records ----
from hermes_os.action_records import ActionRecords


def test_action_records_lifecycle() -> None:
    store = ActionRecords()
    record = store.create("act_1", action_type="search", run_id="run_1")
    assert record.status is ActionStatus.PENDING

    started = store.start("act_1")
    assert started.status is ActionStatus.RUNNING

    done = store.complete("act_1", output_snapshot={"count": 5})
    assert done.status is ActionStatus.COMPLETED
    assert done.output_snapshot == {"count": 5}

    failed = store.fail("act_1", error="timeout")
    assert failed.status is ActionStatus.FAILED
    assert failed.error == "timeout"


# ---- workforce_queue ----
from hermes_os.workforce_queue import WorkforceQueue
from hermes_os.types import WorkforceItem


def test_workforce_queue_priority_and_order() -> None:
    queue = WorkforceQueue()
    a = queue.enqueue(WorkforceItem(item_id="task_a", item_type="task", priority=1))
    b = queue.enqueue(WorkforceItem(item_id="task_b", item_type="task", priority=5))
    c = queue.enqueue(WorkforceItem(item_id="task_c", item_type="task", priority=3))

    first = queue.dequeue()
    assert first is not None
    assert first.item_id == "task_b"  # highest priority wins

    queue.complete("task_b")
    pending = queue.pending()
    assert len(pending) == 2


# ---- control_center_snapshot ----
from hermes_os.control_center_snapshot import ControlCenterSnapshotStore


def test_control_center_snapshot_lifecycle() -> None:
    store = ControlCenterSnapshotStore()
    snap = store.capture(active_runs=3, queued_items=1, health_status="healthy")
    assert store.latest() is snap
    fetched = store.get(snap.snapshot_id)
    assert fetched.active_runs == 3


# ---- operational_memory_log ----
from hermes_os.operational_memory_log import OperationalMemoryLog


def test_operational_memory_log_append_and_query() -> None:
    log = OperationalMemoryLog()
    e1 = log.append(source="runner", category="execution", content="started")
    e2 = log.append(source="runner", category="approval", content="pending")
    assert log.count() == 2

    cat_results = log.query(category="execution")
    assert cat_results == [e1]

    src_results = log.query(source="runner")
    assert src_results == [e1, e2]


# ---- minimal_cli_spec ----
from hermes_os.minimal_cli_spec import CLISpec, CommandSpec, DEFAULT_CLI_SPEC


def test_default_cli_spec_commands() -> None:
    assert "status" in DEFAULT_CLI_SPEC.list_commands()
    assert DEFAULT_CLI_SPEC.commands["status"].name == "status"
    assert DEFAULT_CLI_SPEC.binary_name == "hermes-os"

    custom = CLISpec(binary_name="custom")
    custom.register(CommandSpec("greet", "Greet a user"))
    assert custom.list_commands() == ["greet"]
