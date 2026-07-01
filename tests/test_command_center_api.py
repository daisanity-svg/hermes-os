"""Tests for Command Center v1 nucleus — adapter + API."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import HTTPServer
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from hermes_os.command_center.adapter import CommandCenterAdapter
from hermes_os.command_center.api import _CommandCenterHandler, run
from hermes_os.org_learning.signals import SignalCategory
from hermes_os.org_learning.providers import SignalRegistry


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def live_server():
    port = _free_port()
    server = run(host="127.0.0.1", port=port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestCommandCenterAdapter:
    def test_get_overview_returns_expected_keys(self) -> None:
        adapter = CommandCenterAdapter()
        result = adapter.get_overview()
        assert "executive_brief" in result
        assert "department_health" in result
        assert "decision_queue" in result
        assert "company_health" in result

    def test_get_executive_brief_filters_high_confidence(self) -> None:
        adapter = CommandCenterAdapter()
        brief = adapter.get_executive_brief()
        for item in brief:
            assert item["confidence"] >= 0.85 or item["priority_for_chairman"] is True

    def test_get_department_health_default_engineering(self) -> None:
        adapter = CommandCenterAdapter()
        result = adapter.get_department_health("engineering")
        assert result["department"] == "engineering"
        assert "overall_score" in result
        assert "signals" in result
        assert len(result["signals"]) >= 1

    def test_get_department_health_low_score_marks_priority(self) -> None:
        adapter = CommandCenterAdapter()
        bad_metrics = {
            "velocity": {"delivered": 0.0, "planned": 1.0},
            "quality": {"defect_rate": 0.5},
            "stability": {"incidents": 20.0},
            "alignment": {"goal_hit_rate": 0.0},
            "capacity": {"utilization": 0.0},
        }
        result = adapter.get_department_health("ops", metrics=bad_metrics)
        signals = result["signals"]
        assert any(s["priority_for_chairman"] for s in signals)

    def test_get_decision_queue_empty_returns_empty(self) -> None:
        adapter = CommandCenterAdapter()
        signals = adapter.get_decision_queue_signals()
        assert signals == []

    def test_get_decision_queue_with_pending_tickets(self) -> None:
        tickets = [
            {
                "ticket_id": "t1",
                "title": "Q3 預算簽核",
                "description": "行銷部提問 Q3 預算重新分配",
                "department": "行銷",
                "status": "PENDING",
                "created_at": "2026-06-25T14:00:00",
            }
        ]
        adapter = CommandCenterAdapter()
        signals = adapter.get_decision_queue_signals(pending_tickets=tickets)
        assert len(signals) == 1
        assert signals[0]["category"] == "Risk"
        assert signals[0]["priority_for_chairman"] is True

    def test_get_company_health_aggregates_signals(self) -> None:
        adapter = CommandCenterAdapter()
        result = adapter.get_company_health()
        assert "total_signals" in result
        assert "priority_count" in result
        assert "high_confidence_count" in result
        assert "by_category" in result
        assert "dimension_scores" in result

    def test_get_reliability_overview_returns_counts(self) -> None:
        adapter = CommandCenterAdapter()
        result = adapter.get_reliability_overview()
        assert "counts" in result
        assert "recent_abnormal" in result
        assert "founder_tickets" in result
        for key in ("running", "completed", "failed", "lost", "recovering", "needs_founder_decision"):
            assert key in result["counts"]
            assert isinstance(result["counts"][key], int)


class TestCommandCenterAPI:
    def test_overview_endpoint(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/overview"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "executive_brief" in data
        assert "company_health" in data

    def test_executive_brief_endpoint(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/executive-brief"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert isinstance(data, list)

    def test_department_health_endpoint(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/department-health"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert data["department"] == "engineering"
        assert "signals" in data

    def test_decision_queue_endpoint(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/decision-queue"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert isinstance(data, list)

    def test_company_health_endpoint(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/company-health"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "total_signals" in data
        assert "by_category" in data

    def test_unknown_path_returns_404(self, live_server: str) -> None:
        import urllib.request
        import urllib.error

        url = f"{live_server}/api/v1/command-center/unknown"
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url)
        assert exc.value.code == 404

    def test_root_serves_chairman_desktop(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/"
        with urllib.request.urlopen(url) as resp:
            body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        assert "Chairman Desktop" in body

    def test_department_health_accepts_query_param(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/department-health?department=marketing"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert data["department"] == "marketing"

    def test_reliability_endpoint_returns_counts(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/reliability"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "counts" in data
        assert "recent_abnormal" in data
        assert "founder_tickets" in data

    def test_reliability_counts_are_numeric(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/reliability"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        for key in ("running", "completed", "failed", "lost", "recovering", "needs_founder_decision"):
            assert isinstance(data["counts"].get(key), int)


class TestCommandCenterHostBinding:
    def test_run_accepts_configurable_host_0_0_0_0(self) -> None:
        port = _free_port()
        server = run(host="0.0.0.0", port=port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        assert server.server_address[0] == "0.0.0.0"
        assert server.server_address[1] == port
        server.shutdown()

    def test_run_accepts_configurable_host_localhost(self) -> None:
        port = _free_port()
        server = run(host="127.0.0.1", port=port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_address[1] == port
        server.shutdown()

    def test_run_accepts_configurable_host_and_port(self) -> None:
        port = _free_port()
        server = run(host="127.0.0.1", port=port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        assert server.server_address == ("127.0.0.1", port)
        server.shutdown()


class TestCommandCenterApprovalAPI:
    def test_approvals_endpoint_returns_empty_by_default(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/approvals"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "pending_approvals" in data
        assert "waiting_for_approval_runs" in data
        assert "total_pending" in data
        assert data["total_pending"] == 0

    def test_v1_approvals_alias_returns_empty(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/v1/approvals"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "pending_approvals" in data
        assert "waiting_for_approval_runs" in data

    def test_approve_run_updates_journal_and_adapter(self, live_server: str) -> None:
        import urllib.request
        from hermes_os.command_center.api import _CommandCenterHandler

        # Use the handler's shared instances so the API sees the same state.
        journal = _CommandCenterHandler._run_journal
        adapter = _CommandCenterHandler._process_adapter
        approval = _CommandCenterHandler._approval_records

        # Reset just this run to keep other tests isolated
        journal.update("approval-run-1", status="cancelled") if journal.get("approval-run-1") else None
        adapter._run_registry.pop("item-1", None)
        approval._records.pop("item-1", None)
        approval._records.pop("approval-run-1", None)

        journal.append(
            run_id="approval-run-1",
            task_name="審批測試任務",
            status="waiting_for_approval",
        )
        adapter.submit({
            "id": "item-1",
            "type": "task",
            "priority": 1,
            "run_id": "approval-run-1",
            "approval_status": "pending",
            "payload": {},
        })
        approval.start("item-1")

        url = f"{live_server}/v1/runs/approval-run-1/approve"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        assert data["run_id"] == "approval-run-1"
        assert data["action"] == "approve"
        assert data["approved_count"] >= 1

    def test_reject_run_returns_rejected_count(self, live_server: str) -> None:
        import urllib.request
        from hermes_os.command_center.api import _CommandCenterHandler

        journal = _CommandCenterHandler._run_journal
        adapter = _CommandCenterHandler._process_adapter
        approval = _CommandCenterHandler._approval_records

        journal.update("reject-run-1", status="cancelled") if journal.get("reject-run-1") else None
        adapter._run_registry.pop("item-2", None)
        approval._records.pop("item-2", None)
        approval._records.pop("reject-run-1", None)

        journal.append(
            run_id="reject-run-1",
            task_name="駁回測試任務",
            status="waiting_for_approval",
        )
        adapter.submit({
            "id": "item-2",
            "type": "task",
            "priority": 1,
            "run_id": "reject-run-1",
            "approval_status": "pending",
            "payload": {},
        })
        approval.start("item-2")

        url = f"{live_server}/v1/runs/reject-run-1/reject"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        assert data["run_id"] == "reject-run-1"
        assert data["action"] == "reject"

    def test_approve_missing_run_returns_404(self, live_server: str) -> None:
        import urllib.request
        import urllib.error

        url = f"{live_server}/v1/runs/does-not-exist/approve"
        req = urllib.request.Request(url, method="POST")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 404


class TestCDLEndpoint:
    def test_cdl_endpoint_returns_overview(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/cdl"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "project_code" in data
        assert "loop_state" in data
        assert "recent_runs" in data

    def test_cdl_filters_by_project_code(self, live_server: str) -> None:
        import urllib.request
        from hermes_os.command_center.api import _CommandCenterHandler

        journal = _CommandCenterHandler._run_journal
        journal.append(run_id="run-cdl-1", task_name="t1", status="completed", project_code="proj-a")
        journal.append(run_id="run-cdl-2", task_name="t2", status="completed", project_code="proj-b")

        try:
            url = f"{live_server}/api/cdl?project_code=proj-a"
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read())
            assert data["project_code"] == "proj-a"
            assert len(data["recent_runs"]) >= 1
            assert all(r["project_code"] == "proj-a" for r in data["recent_runs"])
        finally:
            journal._entries.pop("run-cdl-1", None)
            journal._entries.pop("run-cdl-2", None)

    def test_cdl_default_project_code_is_canonical(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/cdl"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert data["project_code"] == "hermes-os"


class TestCosEndpoints:
    def test_cos_status_endpoint_returns_operational_status(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/cos-status"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "operational_status" in data
        assert "idle_reason" in data
        assert data["operational_status"] in ("idle", "running", "blocked", "waiting_founder", "error")
        assert "cos_state" in data
        assert "loop_state" in data

    def test_cos_progress_endpoint_returns_progress_report(self, live_server: str) -> None:
        import urllib.request

        url = f"{live_server}/api/v1/command-center/cos/progress"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
        assert "project_code" in data
        assert "completed" in data
