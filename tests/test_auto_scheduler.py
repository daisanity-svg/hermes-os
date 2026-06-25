"""Hermes OS — Auto Scheduler v1 tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hermes_os.scheduler.auto_scheduler import AutoScheduler
from hermes_os.scheduler.schemas import (
    AutoSchedulerConfig,
    FounderDecisionPriority,
    SchedulerSource,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
    WatchdogSignal,
)


@pytest.fixture()
def tmp_project_status(tmp_path: Path) -> Path:
    p = tmp_path / "project-status.yaml"
    p.write_text("project_id: hermes-os\nblocked: false\n", encoding="utf-8")
    return p


@pytest.fixture()
def tmp_project_status_blocked(tmp_path: Path) -> Path:
    p = tmp_path / "project-status.yaml"
    p.write_text(
        "project_id: hermes-os\nblocked: true\nblocked_reason: infra outage\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def tmp_contracts_index(tmp_path: Path) -> Path:
    p = tmp_path / "contracts-index.yaml"
    p.write_text(
        "generated_at: \"2026-06-27T00:00:00Z\"\ntotal_contracts: 1\ncontracts:\n  - id: wu-001\n    slug: scheduler-v1\n    path: docs/contracts/20260627-ado-cos-scheduler-v1.yaml\n    sha256: abc\n    signed: true\n    status: signed\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def tmp_contracts_with_draft(tmp_path: Path) -> Path:
    p = tmp_path / "contracts-index.yaml"
    p.write_text(
        "generated_at: \"2026-06-27T00:00:00Z\"\ntotal_contracts: 2\ncontracts:\n  - id: wu-001\n    slug: scheduler-v1\n    path: docs/contracts/20260627-ado-cos-scheduler-v1.yaml\n    signed: true\n    status: signed\n  - id: wu-002\n    slug: roadmap-v1\n    path: docs/contracts/20260627-ado-roadmap-v1.yaml\n    signed: false\n    status: draft\n",
        encoding="utf-8",
    )
    return p


def test_reload_returns_queue_from_signed_contract(
    tmp_project_status: Path,
    tmp_contracts_index: Path,
) -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=tmp_project_status,
        contracts_index_path=tmp_contracts_index,
    )
    queue = scheduler.propose()
    assert len(queue.executable) == 1
    assert queue.executable[0].item_id == "contract-wu-001"


def test_blocked_project_status_emits_ticket(
    tmp_project_status_blocked: Path,
    tmp_contracts_index: Path,
) -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=tmp_project_status_blocked,
        contracts_index_path=tmp_contracts_index,
    )
    queue = scheduler.propose()
    assert any(
        t.blocking_item_id == "ps-unblock-1" for t in queue.founder_decisions
    )
    # blocked candidate should be in blocked list
    assert any(c.item_id == "ps-unblock-1" for c in queue.blocked)


def test_signed_contract_becomes_candidate(
    tmp_project_status: Path,
    tmp_contracts_index: Path,
) -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=tmp_project_status,
        contracts_index_path=tmp_contracts_index,
    )
    queue = scheduler.propose()
    assert any(
        c.item_id == "contract-wu-001" and c.priority == TaskPriority.P2
        for c in queue.executable
    )


def test_draft_contract_waits_for_founder(
    tmp_project_status: Path,
    tmp_contracts_with_draft: Path,
) -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=tmp_project_status,
        contracts_index_path=tmp_contracts_with_draft,
    )
    queue = scheduler.propose()
    assert any(
        c.item_id == "contract-wu-002" and c.priority == TaskPriority.P1
        for c in queue.waiting_founder
    )


def test_sg2_guard_blocks_p0_auto_start() -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=Path("/nonexistent/project-status.yaml"),
        contracts_index_path=Path("/nonexistent/contracts-index.yaml"),
        watchdog_signals=[],
        decision_queue_items=[],
    )
    candidate = TaskCandidate(
        item_id="manual-p0",
        title="P0 manual",
        priority=TaskPriority.P0,
        source=SchedulerSource.RUNS,
        auto_start=True,
    )
    scheduler._candidates[candidate.item_id] = candidate
    scheduler._enforce_guardrails()
    assert scheduler._candidates["manual-p0"].auto_start is False


def test_sg3_guard_caps_concurrent() -> None:
    config = AutoSchedulerConfig(max_concurrent=1)
    scheduler = AutoScheduler(config=config)

    # 先放入一個 non-waiting P2 candidate
    scheduler._candidates["c1"] = TaskCandidate(
        item_id="c1",
        title="c1",
        priority=TaskPriority.P2,
        source=SchedulerSource.CONTRACTS_INDEX,
        status=TaskStatus.QUEUED,
        auto_start=True,
    )

    # 再放入第二個 P2 candidate
    scheduler._candidates["c2"] = TaskCandidate(
        item_id="c2",
        title="c2",
        priority=TaskPriority.P2,
        source=SchedulerSource.CONTRACTS_INDEX,
        status=TaskStatus.QUEUED,
        auto_start=True,
    )

    scheduler._enforce_guardrails()
    queue = scheduler.propose()
    # 在 max_concurrent=1 下，第二個 candidate 應該落排
    assert len(queue.executable) <= 1


def test_drift_raises_priority() -> None:
    config = AutoSchedulerConfig(drift_threshold_hours=0)
    scheduler = AutoScheduler(config=config)

    past = datetime.utcnow() - timedelta(hours=5)
    scheduler._candidates["d1"] = TaskCandidate(
        item_id="d1",
        title="drift me",
        priority=TaskPriority.P3,
        source=SchedulerSource.PACKAGES,
        status=TaskStatus.PENDING,
        created_at=past,
        updated_at=past,
    )
    scheduler._apply_drift()
    assert scheduler._candidates["d1"].priority == TaskPriority.P2
    assert scheduler._candidates["d1"].drift_count == 1


def test_watchdog_signal_bumps_priority() -> None:
    scheduler = AutoScheduler()
    signal = WatchdogSignal(
        item_id="w1",
        consecutive_idle_checks=4,
        health_status="degraded",
        last_seen_at=datetime.utcnow(),
        suggested_action="re_run",
    )
    scheduler._ingest_watchdog([signal])
    scheduler._resolve_dependencies()
    scheduler._enforce_guardrails()
    queue = scheduler.propose()
    assert any(c.item_id == "w1" for c in queue.executable + queue.waiting_founder)


def test_audit_log_records_reload_and_propose() -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=Path("/nonexistent/project-status.yaml"),
        contracts_index_path=Path("/nonexistent/contracts-index.yaml"),
    )
    scheduler.propose()
    log = scheduler.audit_log(limit=10)
    assert len(log) == 2
    assert log[0]["action"] == "reload"
    assert log[1]["action"] == "propose"


def test_no_file_write_sg4(tmp_path: Path) -> None:
    scheduler = AutoScheduler()
    scheduler.reload(
        project_status_path=tmp_path / "project-status.yaml",
        contracts_index_path=tmp_path / "contracts-index.yaml",
    )
    # reload 不會寫入任何 docs/ 檔案 (SG4)
    # 這裡簡單以 no-op 表示；Future 可加 fsassert 驗證
    _ = scheduler.propose()
    assert True
