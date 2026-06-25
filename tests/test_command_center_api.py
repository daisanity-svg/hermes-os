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
