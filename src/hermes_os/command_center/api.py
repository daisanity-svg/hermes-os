"""Command Center HTTP API — minimal built-in server for Founder/Chairman view."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from hermes_os.command_center.adapter import CommandCenterAdapter


class _CommandCenterHandler(BaseHTTPRequestHandler):
    adapter = CommandCenterAdapter()
    _html_path = Path(__file__).resolve().parents[3] / "docs" / "command-center" / "index.html"

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int = 200) -> None:
        try:
            content = self._html_path.read_text(encoding="utf-8")
        except Exception:
            content = "<h1>Command Center</h1><p>找不到頁面檔案。</p>"
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(200)
            return

        routes = {
            "/api/v1/command-center/overview": self.adapter.get_overview,
            "/api/v1/command-center/executive-brief": self.adapter.get_executive_brief,
            "/api/v1/command-center/company-health": self.adapter.get_company_health,
            "/api/v1/command-center/decision-queue": self.adapter.get_decision_queue_signals,
            "/api/v1/command-center/projects": self.adapter.get_active_projects,
            "/api/v1/command-center/workflows": self.adapter.get_active_workflows,
            "/api/v1/command-center/runs": self.adapter.get_runs_mirror,
            "/api/v1/command-center/scheduler": self.adapter.get_scheduler_queue,
            "/api/v1/command-center/inbox": self.adapter.get_founder_inbox,
            "/api/v1/command-center/packages": self.adapter.get_package_timeline,
        }
        if path == "/api/v1/command-center/department-health":
            params = parse_qs(urlparse(self.path).query)
            department = (params.get("department") or ["engineering"])[0]
            try:
                result = self.adapter.get_department_health(department=department)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": f"讀取部門資料失敗：{exc}"})
                return
            self._send_json(200, result)
            return

        handler = routes.get(path)
        if handler is None:
            self._send_json(404, {"error": f"找不到路徑：{path}"})
            return
        try:
            result = handler()
            self._send_json(200, result)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"後端錯誤：{exc}"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # suppress noisy logs during tests
        pass


def run(host: str = "127.0.0.1", port: int = 8765) -> HTTPServer:
    server = HTTPServer((host, port), _CommandCenterHandler)
    return server


if __name__ == "__main__":
    server = run()
    print(f"Command Center API listening on http://{server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
