"""Tests for Workspace PWA Notification Sprint v1."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from http.server import HTTPServer
from urllib.request import urlopen

import pytest

from hermes_os.command_center.api import run
from hermes_os.scheduler.schemas import SortedTaskQueue, FounderDecisionTicket, TaskCandidate, TaskPriority, TaskStatus, FounderDecisionPriority, SchedulerSource


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


class TestPWAStaticAssets:
    def test_manifest_json_served(self, live_server: str) -> None:
        with urlopen(f"{live_server}/manifest.json") as resp:
            data = json.loads(resp.read())
        assert data["name"] == "Chairman Desktop"
        assert data["short_name"] == "Chairman"
        assert data["display"] == "standalone"
        assert "icons" in data

    def test_sw_js_served(self, live_server: str) -> None:
        with urlopen(f"{live_server}/sw.js") as resp:
            body = resp.read().decode("utf-8")
        assert "CACHE_NAME" in body
        assert "notificationclick" in body

    def test_icon_svg_served(self, live_server: str) -> None:
        with urlopen(f"{live_server}/icon.svg") as resp:
            data = resp.read()
        assert b"svg" in data[:40].lower() or b"<svg" in data[:40].lower()

    def test_manifest_has_valid_scheme(self, live_server: str) -> None:
        with urlopen(f"{live_server}/manifest.json") as resp:
            data = json.loads(resp.read())
        assert data["start_url"].startswith("/") or data["start_url"].startswith("http")


class TestCommandCenterNotificationUI:
    HTML_PATH = Path(__file__).resolve().parents[1] / "docs" / "command-center" / "index.html"

    def _read_html(self) -> str:
        return self.HTML_PATH.read_text(encoding="utf-8")

    def test_pwa_meta_tags_present(self) -> None:
        html = self._read_html()
        assert '<meta name="theme-color" content="#0066cc" />' in html
        assert '<link rel="manifest" href="/manifest.json" />' in html
        assert '<link rel="icon" href="/icon.svg" type="image/svg+xml" />' in html
        assert 'apple-mobile-web-app-capable' in html

    def test_notification_controls_present(self) -> None:
        html = self._read_html()
        assert 'id="btn-notify-enable"' in html
        assert 'id="btn-notify-disable"' in html
        assert 'id="notify-status"' in html

    def test_notification_js_present(self) -> None:
        html = self._read_html()
        assert "CCNotify" in html
        assert "Notification.requestPermission" in html
        assert "scrollToSection" in html
        assert "ws-runs" in html
        assert "ws-inbox" in html
        assert "ws-scheduler" in html

    def test_service_worker_registration_present(self) -> None:
        html = self._read_html()
        assert "serviceWorker.register('/sw.js')" in html

    def test_toast_fallback_present(self) -> None:
        html = self._read_html()
        assert "cc-toast" in html
        assert "站內提醒" in html or "站內提醒" in html

    def test_required_module_ids_still_present(self) -> None:
        html = self._read_html()
        required = {
            "panel-company", "panel-brief", "panel-department", "panel-decision",
            "ws-projects", "ws-workflows", "ws-runs", "ws-reliability", "ws-scheduler", "ws-inbox", "ws-packages",
        }
        missing = {mid for mid in required if f'id="{mid}"' not in html}
        assert not missing, f"Missing required module IDs: {missing}"

    def test_no_engineering_jargon_in_headings(self) -> None:
        html = self._read_html()
        import re
        headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.DOTALL)
        plain_headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings]
        forbidden = {"Auto Scheduler", "Hermes Runs Mirror", "Active Projects", "Active Workflows", "Package Timeline"}
        bad = [h for h in plain_headings if h in forbidden]
        assert not bad, f"Engineering jargon still present in headings: {bad}"

    def test_friendly_terms_present(self) -> None:
        html = self._read_html()
        friendly = {"進行中專案", "進行中流程", "系統執行記錄", "任務待辦", "可靠性狀態", "套件時程", "Founder Inbox"}
        missing = {t for t in friendly if t not in html}
        assert not missing, f"Expected friendly terms missing: {missing}"


class TestAdapterNotificationData:
    def test_runs_mirror_provides_status(self) -> None:
        from hermes_os.command_center.adapter import CommandCenterAdapter
        adapter = CommandCenterAdapter()
        data = adapter.get_runs_mirror()
        assert "runs" in data
        for r in data["runs"]:
            assert "run_id" in r
            assert "status" in r
            assert r["status"] in {"running", "completed", "failed", "pending", "needs_founder_decision", "cancelled", "queued", "stopping", "waiting_for_approval", "recovering", "lost"}

    def test_founder_inbox_provides_pending_tickets(self) -> None:
        from hermes_os.command_center.adapter import CommandCenterAdapter
        adapter = CommandCenterAdapter()
        data = adapter.get_founder_inbox()
        assert "tickets" in data
        for t in data["tickets"]:
            assert "ticket_id" in t
            assert "title" in t
            assert "status" in t

    def test_scheduler_queue_has_founder_decisions(self) -> None:
        from hermes_os.command_center.adapter import CommandCenterAdapter
        adapter = CommandCenterAdapter()
        data = adapter.get_scheduler_queue()
        assert "waiting_founder" in data
        assert "founder_decisions" in data
        assert isinstance(data["waiting_founder"], list)
        assert isinstance(data["founder_decisions"], list)
