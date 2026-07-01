"""Hermes OS — CoS Operating Runtime v1 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from hermes_os.cos_runtime import CosRuntime, CosState
from hermes_os.run_journal import RunJournal
from hermes_os.scheduler.schemas import TaskPriority


class _FakeAdapter:
    """Fake adapter that simulates successful execution for all submitted tasks."""

    def __init__(self) -> None:
        self.submitted: list = []
        self.completed: list = []

    def submit(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self.submitted.append(item)
        return {"status": "queued", "workforce_item_id": item["id"]}

    def complete(self, item_id: str) -> Dict[str, Any]:
        self.completed.append(item_id)
        return {"status": "completed"}

    def drain(self, limit: int = 1):  # pragma: no cover - not used in mock path
        return []


@pytest.fixture()
def fake_adapter() -> _FakeAdapter:
    return _FakeAdapter()


@pytest.fixture()
def cos_factory(fake_adapter: _FakeAdapter, tmp_path: Path):
    def _make(**kwargs: Any) -> CosRuntime:
        journal_path = kwargs.pop("storage_path", tmp_path / "journal-cos.json")
        next_tasks_path = kwargs.pop(
            "next_tasks_path",
            tmp_path / "next_tasks.yaml",
        )
        # write a minimal next_tasks.yaml if path does not exist or empty
        if not next_tasks_path.exists():
            next_tasks_path.parent.mkdir(parents=True, exist_ok=True)
            next_tasks_path.write_text(
                "project_code: test-proj\nproject_name: Test Project\nmax_tasks_per_cycle: 2\ntasks:\n"
                "  - item_id: t1\n"
                "    title: Task One\n"
                "    priority: P3\n"
                "    source: next-tasks\n"
                "    status: queued\n"
                "    auto_start: true\n"
                "    metadata: {}\n"
                "  - item_id: t2\n"
                "    title: Task Two\n"
                "    priority: P3\n"
                "    source: next-tasks\n"
                "    status: queued\n"
                "    auto_start: true\n"
                "    metadata: {}\n",
                encoding="utf-8",
            )
        return CosRuntime(
            adapter=fake_adapter,
            storage_path=journal_path,
            next_tasks_path=next_tasks_path,
            **kwargs,
        )

    return _make


def _make_task_file(path: Path, tasks: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "project_code: ado-workspace",
        "project_name: ADO Workspace",
        "max_tasks_per_cycle: 2",
        "tasks:",
    ]
    for t in tasks:
        lines.append(
            f"  - item_id: {t['id']}\n"
            f"    title: {t['title']}\n"
            f"    priority: {t.get('priority', 'P3')}\n"
            f"    source: next-tasks\n"
            f"    status: queued\n"
            f"    auto_start: true\n"
            f"    metadata: {{}}\n"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


class TestCosRuntime:
    def test_run_once_completes_tasks_and_updates_journal(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        result = rt.run_once()
        entries = rt._journal.list()
        assert result["state"] == CosState.STOPPED.value
        assert len(entries) == 2
        assert entries[0].status == "completed"
        assert entries[0].task_name == "Task One"
        assert entries[1].task_name == "Task Two"

    def test_max_tasks_per_cycle_is_respected(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "a1", "title": "A1"},
                {"id": "a2", "title": "A2"},
                {"id": "a3", "title": "A3"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=2,
        )
        result = rt.run_once()
        assert result["state"] == CosState.STOPPED.value
        assert fake_adapter.submitted.__len__() == 2

    def test_progress_report_generated_after_run(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        rt.run_once()
        progress = rt.progress()
        assert "completed" in progress
        assert len(progress["completed"]) == 2
        assert progress["project_code"] == "test-proj"
        assert rt._state == CosState.STOPPED

    def test_founder_ticket_stops_loop_for_p0(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {
                    "id": "p0-1",
                    "title": "High Risk",
                    "priority": "P0",
                }
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
        )
        result = rt.run_once()
        assert result["state"] == CosState.BLOCKED.value
        assert result["loop"]["stop_reason"] == "founder_decision_required"

    def test_list_next_tasks_returns_backlog(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        tasks = rt.list_next_tasks()
        assert len(tasks) == 2
        assert tasks[0]["item_id"] == "t1"
        assert tasks[1]["title"] == "Task Two"

    def test_status_returns_snapshot(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        status = rt.status()
        assert "cos_state" in status
        assert status["project_code"] == "test-proj"
        assert "loop" in status

    def test_run_once_writes_progress_report_file(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        rt.run_once()
        report_dir = tmp_path / "progress-reports"
        assert report_dir.exists()
        reports = list(report_dir.glob("*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "Chairman Progress Report" in content
        assert "Task One" in content or "Task Two" in content

    def test_daemon_stops_after_max_tasks_per_session(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "s1", "title": "S1"},
                {"id": "s2", "title": "S2"},
                {"id": "s3", "title": "S3"},
                {"id": "s4", "title": "S4"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=2,
            stop_on_failure=True,
            stop_on_founder_decision=True,
        )
        result = rt.daemon_run(interval=0)
        assert result["session"]["total_executed"] == 2
        assert result["session"]["stop_reason"] == "max_tasks_per_session"

    def test_daemon_writes_founder_inbox_on_stop(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "p0-1", "title": "High Risk", "priority": "P0"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=3,
            stop_on_failure=True,
            stop_on_founder_decision=True,
        )
        result = rt.daemon_run(interval=0)
        inbox = tmp_path / "founder-inbox.yaml"
        assert inbox.exists()
        import yaml
        data = yaml.safe_load(inbox.read_text(encoding="utf-8")) or {}
        assert len(data.get("tickets", [])) >= 1

    def test_daemon_stops_on_founder_decision_when_flag_set(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "p0-1", "title": "High Risk", "priority": "P0"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=5,
            stop_on_failure=True,
            stop_on_founder_decision=True,
        )
        result = rt.daemon_run(interval=0)
        assert result["session"]["stop_reason"] == "founder_decision_required"

    def test_daemon_reports_no_tasks_when_empty(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        # all tasks completed
        _make_task_file(
            next_path,
            [
                {"id": "done1", "title": "Done", "priority": "P3", "status": "completed"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=2,
            stop_on_failure=True,
            stop_on_founder_decision=False,
        )
        result = rt.daemon_run(interval=0)
        assert result["session"]["stop_reason"] == "no_tasks"

    def test_daemon_continues_while_tasks_exist(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "c1", "title": "C1", "priority": "P3"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=2,
            stop_on_failure=True,
            stop_on_founder_decision=False,
        )
        result = rt.daemon_run(interval=0)
        # one cycle runs 1 task, then no_tasks stops
        assert result["session"]["stop_reason"] == "no_tasks"
        assert result["session"]["total_executed"] == 1

    def test_status_includes_operational_status_and_idle_reason(self, cos_factory, tmp_path: Path) -> None:
        rt = cos_factory(storage_path=tmp_path / "journal.json")
        status = rt.status()
        assert "operational_status" in status
        assert "idle_reason" in status
        assert status["operational_status"] == "idle"
        assert status["idle_reason"] == "尚未啟動"

    def test_operational_status_is_idle_after_no_tasks(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [{"id": "done1", "title": "Done", "priority": "P3", "status": "completed"}],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
            max_tasks_per_session=2,
        )
        rt.run_once()
        status = rt.status()
        assert status["operational_status"] == "idle"
        assert status["idle_reason"] == "目前無安全任務可執行"

    def test_operational_status_is_waiting_founder_for_p0(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [{"id": "p0-1", "title": "High Risk", "priority": "P0"}],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
        )
        rt.run_once()
        status = rt.status()
        assert status["operational_status"] == "waiting_founder"
        assert status["idle_reason"] == "等待 Founder 決策後才可繼續"

    def test_cos_runtime_status_run_once_daemon_share_top_level_contract(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [
                {"id": "t1", "title": "T1", "priority": "P3"},
                {"id": "t2", "title": "T2", "priority": "P3"},
            ],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=2,
            max_tasks_per_session=10,
        )

        status_payload = rt.status()
        run_once_payload = rt.run_once()

        expected_top = {
            "schema_version",
            "state",
            "session",
            "report",
            "progress",
            "loop",
            "cos_runtime",
        }
        assert expected_top.issubset(set(status_payload.keys()))
        assert expected_top.issubset(set(run_once_payload.keys()))

        daemon_payload = rt.daemon_run(interval=0)
        assert expected_top.issubset(set(daemon_payload.keys()))

    def test_status_retains_chairman_compat_keys(self, fake_adapter, tmp_path: Path) -> None:
        next_path = tmp_path / "next.yaml"
        _make_task_file(
            next_path,
            [{"id": "t1", "title": "T1", "priority": "P3"}],
        )
        rt = CosRuntime(
            adapter=fake_adapter,
            storage_path=tmp_path / "journal.json",
            next_tasks_path=next_path,
            max_tasks_per_cycle=1,
        )
        rt.run_once()
        status = rt.status()
        assert "needs_founder_intervention" in status
        assert "next_suggestion" in status
        assert "idle_reason" in status
        assert status["needs_founder_intervention"] in {True, False}
        assert status["next_suggestion"] is None or isinstance(status["next_suggestion"], str)
        assert status["idle_reason"] is None or isinstance(status["idle_reason"], str)
