"""Command Center HTTP API — minimal built-in server for Founder/Chairman view."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from hermes_os.approval_records import ApprovalRecords
from hermes_os.command_center.adapter import CommandCenterAdapter
from hermes_os.continuous_loop import ContinuousDevelopmentLoop
from hermes_os.cos_runtime import CosRuntime
from hermes_os.process_adapter import ProcessAdapter
from hermes_os.run_journal import RunJournal
from hermes_os.run_registry import RunRegistry
from hermes_os.run_journal_jsonl import JsonlRunJournal


class _CommandCenterHandler(BaseHTTPRequestHandler):
    adapter = CommandCenterAdapter()
    _approval_records = ApprovalRecords()
    _process_adapter = ProcessAdapter(approval_records=_approval_records)
    _loop = ContinuousDevelopmentLoop(adapter=_process_adapter)
    _run_journal = RunJournal()
    _cos_runtime = CosRuntime()
    _run_registry = RunRegistry()
    _jsonl_journal = JsonlRunJournal()
    _html_path = Path(__file__).resolve().parents[3] / "docs" / "command-center" / "index.html"
    _static_dir = Path(__file__).resolve().parents[3] / "docs" / "command-center"

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

    def _send_static(self, filename: str) -> None:
        path = self._static_dir / filename
        if not path.exists() or not path.is_file():
            self._send_json(404, {"error": f"找不到靜態檔案：{filename}"})
            return
        content_type = {
            ".json": "application/json; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(path.suffix, "application/octet-stream")
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"讀取靜態檔案失敗：{exc}"})

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
            "/api/v1/command-center/reliability": self.adapter.get_reliability_overview,
            "/api/v1/command-center/scheduler": self.adapter.get_scheduler_queue,
            "/api/v1/command-center/inbox": self.adapter.get_founder_inbox,
            "/api/v1/command-center/packages": self.adapter.get_package_timeline,
            "/api/v1/command-center/loop": self.adapter.get_loop_status,
            "/api/v1/command-center/loop/progress": self.adapter.get_loop_progress,
            "/api/v1/command-center/cos-status": self.adapter.get_cos_status,
            "/api/v1/command-center/cos/progress": self.adapter.get_cos_progress,
            "/api/v1/command-center/ai-team-status": self.adapter.get_ai_team_status,
            "/api/v1/command-center/system-status": lambda: {"connected": True},
            "/api/v1/command-center/switch-project": self.adapter.switch_project,
            "/api/v1/command-center/approvals": self._get_approvals,
            "/api/cdl": self._get_cdl_overview,
        }

        # PWA static assets
        if path == "/manifest.json":
            self._send_static("manifest.json")
            return
        if path == "/sw.js":
            self._send_static("sw.js")
            return
        if path == "/icon.svg":
            self._send_static("icon.svg")
            return
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
            # Support /v1/approvals alias
            if path == "/v1/approvals":
                try:
                    result = self._get_approvals()
                    self._send_json(200, result)
                except Exception as exc:  # noqa: BLE001
                    self._send_json(500, {"error": f"後端錯誤：{exc}"})
                return
            # /api/v1/runs - list runs
            run_list_match = re.match(r"^/api/v1/runs$", path)
            run_wait_match = re.match(r"^/api/v1/runs/([^/]+)/wait$", path)
            artifacts_list_match = re.match(r"^/api/v1/runs/([^/]+)/artifacts$", path)
            artifact_download_match = re.match(r"^/api/v1/runs/([^/]+)/([^/]+)$", path)
            meeting_list_match = re.match(r"^/api/v1/meetings$", path)
            meeting_wait_match = re.match(r"^/api/v1/meetings/([^/]+)/wait$", path)
            if run_list_match:
                try:
                    result = self._handle_list_runs()
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"查詢 run 列表失敗：{exc}"}
                self._send_json(200, result)
                return
            if run_wait_match:
                run_id = run_wait_match.group(1)
                try:
                    result = self._handle_run_wait(run_id)
                    if isinstance(result, dict) and result.get("status") in (None, "queued", "unknown"):
                        completed = self._maybe_execute_run(run_id)
                        if completed:
                            result = self._handle_run_wait(run_id)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"查詢 run 失敗：{exc}"}
                self._send_json(200, result)
                return
            if artifacts_list_match:
                run_id = artifacts_list_match.group(1)
                try:
                    result = self._handle_list_artifacts(run_id)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"查詢 artifacts 失敗：{exc}"}
                self._send_json(200, result)
                return
            if artifact_download_match:
                run_id = artifact_download_match.group(1)
                filename = artifact_download_match.group(2)
                if filename != "artifacts":
                    try:
                        result = self._handle_download_artifact(run_id, filename)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": f"下載 artifact 失敗：{exc}"}
                    self._send_json(200, result)
                    return
            if meeting_list_match:
                try:
                    result = self._list_meetings()
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"查詢會議列表失敗：{exc}"}
                self._send_json(200, result)
                return
            if meeting_wait_match:
                meeting_id = meeting_wait_match.group(1)
                try:
                    result = self._meeting_run_wait(meeting_id)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"查詢會議狀態失敗：{exc}"}
                self._send_json(200, result)
                return
            self._send_json(404, {"error": f"找不到路徑：{path}"})
            return
        try:
            if path in (
                "/api/v1/command-center/loop",
                "/api/v1/command-center/loop/progress",
                "/api/v1/command-center/cos-status",
                "/api/v1/command-center/cos/progress",
            ):
                result = handler(self._cos_runtime)
            else:
                result = handler()
            self._send_json(200, result)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"後端錯誤：{exc}"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # suppress noisy logs during tests
        pass

    def _get_approvals(self) -> Dict[str, Any]:
        # Collect pending approval records
        pending_records = []
        for record in self._approval_records.list_pending():
            pending_records.append({
                "item_id": record.item_id,
                "status": record.status,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "metadata": record.metadata,
            })

        # Collect runs waiting for approval from journal and process adapter
        waiting_runs = []
        journal_entries = self._run_journal.list(status="waiting_for_approval")
        for entry in journal_entries:
            waiting_runs.append({
                "run_id": entry.run_id,
                "task_name": entry.task_name,
                "reason": entry.error or entry.next_action or "等待主席審批",
                "status": entry.status,
                "updated_at": entry.updated_at.isoformat() if hasattr(entry.updated_at, "isoformat") else str(entry.updated_at),
                "project_code": entry.project_code,
                "project_name": entry.project_name,
            })

        # Also scan process adapter for items with waiting_for_approval status
        for item_id, entry in self._process_adapter._run_registry.items():
            approval_status = entry.get("approval_status") or entry.get("status")
            if approval_status not in ("pending", "waiting_for_approval"):
                continue
            run_id = entry.get("run_id")
            if not run_id:
                continue
            # Avoid duplicates if already in journal
            if any(r["run_id"] == run_id for r in waiting_runs):
                continue
            waiting_runs.append({
                "run_id": run_id,
                "task_name": entry.get("workforce_item_id", item_id),
                "reason": "等待主席審批",
                "status": approval_status,
                "updated_at": entry.get("status_updated_at"),
                "project_code": None,
                "project_name": None,
            })

        return {
            "pending_approvals": pending_records,
            "waiting_for_approval_runs": waiting_runs,
            "total_pending": len(pending_records) + len(waiting_runs),
        }

    def _get_cdl_overview(self) -> Dict[str, Any]:
        from urllib.parse import parse_qs
        params = parse_qs(urlparse(self.path).query)
        raw_project_code = (params.get("project_code") or [""])[0]
        limit_raw = (params.get("limit") or ["10"])[0]
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 10

        from hermes_os.data import resolve_project_code
        project_code = resolve_project_code(raw_project_code)

        entries = self._run_journal.list(project_code=project_code, limit=limit)
        loop_state = self._loop.status()
        return {
            "project_code": project_code,
            "loop_state": loop_state.get("state"),
            "stop_reason": loop_state.get("stop_reason"),
            "completed_count": loop_state.get("completed_count"),
            "founder_tickets_count": loop_state.get("founder_tickets_count"),
            "recent_runs": [
                {
                    "run_id": e.run_id,
                    "task_name": e.task_name,
                    "status": e.status,
                    "updated_at": e.updated_at.isoformat() if hasattr(e.updated_at, "isoformat") else str(e.updated_at),
                    "project_code": e.project_code,
                    "project_name": e.project_name,
                }
                for e in entries
            ],
        }

    def _handle_approve(self, run_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        # Update run journal if present
        journal_entry = self._run_journal.get(run_id)
        if journal_entry and journal_entry.status in ("waiting_for_approval", "needs_founder_decision"):
            self._run_journal.update(
                run_id,
                status="queued",
                last_event="founder_approved",
                next_action="continue_execution",
            )

        # Approve all matching items in process adapter
        approved: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        for item_id, entry in list(self._process_adapter._run_registry.items()):
            if entry.get("run_id") != run_id:
                continue
            approval_status = entry.get("approval_status") or entry.get("status")
            if approval_status in ("pending", "waiting_for_approval"):
                result = self._process_adapter.approve(item_id)
                if result:
                    approved.append(result)

        # Also approve any standalone approval records keyed by run_id
        record = self._approval_records.get(run_id)
        if record is not None and record.status == "pending":
            self._approval_records.approve(run_id)
            approved.append({"workforce_item_id": run_id, "approval_status": "approved"})

        return {
            "run_id": run_id,
            "action": "approve",
            "approved_count": len(approved),
            "approved_items": approved,
            "updated_at": self._process_adapter._now().isoformat(),
        }

    def _meeting_run_wait(self, meeting_id: str) -> Dict[str, Any]:
        if not meeting_id:
            return {"status": "error", "error": "缺少 meeting_id"}
        return self._run_registry.get(meeting_id) or {
            "meeting_id": meeting_id,
            "status": "unknown",
        }

    def _list_meetings(self) -> Dict[str, Any]:
        from urllib.parse import parse_qs
        params = parse_qs(urlparse(self.path).query)
        project_code = (params.get("project_code") or [""])[0]
        limit_raw = (params.get("limit") or ["20"])[0]
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 20

        rows = []
        for row in self._run_registry._conn.execute(
            "SELECT run_id, status, task_name, updated_at FROM runs WHERE task_name LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (f"meeting-%{project_code}%", limit),
        ).fetchall():
            rows.append(self._run_registry._row_to_dict(row))
        return {"meetings": rows, "count": len(rows)}

    def _handle_list_runs(self) -> Dict[str, Any]:
        rows = []
        for row in self._run_registry._conn.execute(
            "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?",
            (50,),
        ).fetchall():
            rows.append(self._run_registry._row_to_dict(row))
        return {"runs": rows, "count": len(rows)}

    def _handle_run_wait(self, run_id: str) -> Dict[str, Any]:
        row = self._run_registry.get(run_id)
        if not row:
            entry = self._process_adapter._run_registry.get(run_id)
            if not entry:
                event = self._jsonl_journal.latest(run_id)
                if event:
                    row = {
                        "run_id": event.get("run_id", run_id),
                        "status": event.get("status", "unknown"),
                        "task_name": event.get("task_name"),
                        "updated_at": event.get("occurred_at"),
                        "project_code": None,
                        "project_name": None,
                        "found_in": "jsonl_journal",
                    }
                else:
                    row = {"run_id": run_id, "status": "unknown", "found_in": "none"}
            else:
                row = {
                    "run_id": run_id,
                    "status": entry.get("status", "unknown"),
                    "task_name": entry.get("task_name"),
                    "updated_at": entry.get("status_updated_at"),
                    "project_code": None,
                    "project_name": None,
                    "found_in": "process_adapter",
                }
        else:
            row["found_in"] = "sqlite_registry"
        return row

    def _handle_list_artifacts(self, run_id: str) -> Dict[str, Any]:
        from hermes_os.artifact_registry import ArtifactRegistry
        registry = ArtifactRegistry()
        artifacts = registry.list_for_run(run_id)
        items = []
        statuses: Dict[str, int] = {}
        for artifact in artifacts:
            status = "present"
            statuses[status] = statuses.get(status, 0) + 1
            items.append({
                "artifact_id": artifact.artifact_id,
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
                "created_at": artifact.created_at,
                "absolute_path": artifact.absolute_path,
                "signature": artifact.signature,
                "metadata": artifact.metadata,
            })
        return {
            "run_id": run_id,
            "items": items,
            "metadata": {
                "item_count": len(items),
                "statuses": statuses,
                "created_at": artifacts[0].created_at if artifacts else None,
                "updated_at": artifacts[-1].created_at if artifacts else None,
            },
        }

    def _handle_download_artifact(self, run_id: str, filename: str) -> Dict[str, Any]:
        from hermes_os.artifact_registry import ArtifactRegistry
        registry = ArtifactRegistry()
        artifact_id = f"{run_id}::{filename}"
        stored = registry.get(artifact_id)
        if not stored:
            return {"error": f"artifact 不存在：{filename}"}
        target = Path(stored.absolute_path)
        if not target.exists():
            return {"error": f"artifact 檔案不存在：{target}"}
        return {
            "run_id": run_id,
            "filename": stored.filename,
            "content_type": stored.content_type,
            "size_bytes": stored.size_bytes,
            "sha256": stored.sha256,
            "created_at": stored.created_at,
            "absolute_path": stored.absolute_path,
            "signature": stored.signature,
            "metadata": stored.metadata,
        }

    def _maybe_execute_run(self, run_id: str) -> bool:
        from hermes_os.artifact_registry import ArtifactRegistry
        from hermes_os.llm_client import LLMClient
        registry = self._process_adapter._run_registry
        entries = [
            entry for entry in registry.values()
            if entry.get("run_id") == run_id or entry.get("run_id") in (None, "")
        ]
        if not entries:
            entries = [
                entry for entry in registry.values()
                if any(key == run_id for key in (entry.get("run_id"), entry.get("item_id")))
            ]
        if not entries:
            return False
        drained = self._process_adapter.drain(limit=max(1, len(entries)))
        if not drained:
            return False
        try:
            artifact_registry = ArtifactRegistry()
            summary = "\n".join(
                f"{item.get('id')}: {item.get('status')}" for item in drained
            ).encode("utf-8")
            artifact_registry.register(
                run_id=run_id,
                filename="summary.txt",
                content=summary,
                content_type="text/plain",
            )
            client = LLMClient()
            task_name = (entries[0].get("task_name") or run_id).strip()
            prompt = f"请为以下任务产出执行结果摘要：{task_name}\n\n" \
                     f"任务处理结果：\n{summary.decode('utf-8', errors='replace')}"
            response = client.complete(prompt)
            text = (response.get("text") or "").strip()
            if text:
                artifact_registry.register(
                    run_id=run_id,
                    filename="response.txt",
                    content=text.encode("utf-8"),
                    content_type="text/plain; charset=utf-8",
                )
        except Exception:  # noqa: BLE001
            pass
        return True

    def _handle_reject(self, run_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        journal_entry = self._run_journal.get(run_id)
        if journal_entry and journal_entry.status in ("waiting_for_approval", "needs_founder_decision"):
            self._run_journal.update(
                run_id,
                status="cancelled",
                last_event="founder_rejected",
                next_action="none",
            )

        rejected: List[Dict[str, Any]] = []
        for item_id, entry in list(self._process_adapter._run_registry.items()):
            if entry.get("run_id") != run_id:
                continue
            approval_status = entry.get("approval_status") or entry.get("status")
            if approval_status in ("pending", "waiting_for_approval"):
                result = self._process_adapter.reject(item_id)
                if result:
                    rejected.append(result)

        record = self._approval_records.get(run_id)
        if record is not None and record.status == "pending":
            self._approval_records.reject(run_id)
            rejected.append({"workforce_item_id": run_id, "approval_status": "rejected"})

        return {
            "run_id": run_id,
            "action": "reject",
            "rejected_count": len(rejected),
            "rejected_items": rejected,
            "updated_at": self._process_adapter._now().isoformat(),
        }

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        approve_match = re.match(r"^/v1/runs/([^/]+)/approve$", path)
        reject_match = re.match(r"^/v1/runs/([^/]+)/reject$", path)
        cc_approve_match = re.match(r"^/api/v1/command-center/runs/([^/]+)/approve$", path)
        cc_reject_match = re.match(r"^/api/v1/command-center/runs/([^/]+)/reject$", path)
        create_run_match = path in ("/api/v1/runs", "/v1/runs")

        run_id: Optional[str] = None
        action: Optional[str] = None
        if approve_match:
            run_id = approve_match.group(1)
            action = "approve"
        elif reject_match:
            run_id = reject_match.group(1)
            action = "reject"
        elif cc_approve_match:
            run_id = cc_approve_match.group(1)
            action = "approve"
        elif cc_reject_match:
            run_id = cc_reject_match.group(1)
            action = "reject"
        elif create_run_match:
            action = "create_run"
        else:
            self._send_json(404, {"error": f"找不到路徑：{path}"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
        except Exception:
            body = {}

        if action == "create_run":
            translated = dict(body or {})
            if not translated.get("id"):
                base_id = translated.get("task_name") or f"run-{int(self._process_adapter._now().timestamp()*1000)}"
                candidate = base_id
                suffix = 0
                while candidate in self._process_adapter._run_registry:
                    suffix += 1
                    candidate = f"{base_id}-{suffix}"
                translated["id"] = candidate
            if isinstance(translated.get("priority"), str) and translated["priority"].startswith("P"):
                try:
                    translated["priority"] = int(translated["priority"][1:])
                except ValueError:
                    translated["priority"] = 0
            try:
                result = self._process_adapter.createRun(translated)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": f"createRun failed: {exc}"})
                return
            self._send_json(200, result)
            return

        if run_id is None or action is None:
            self._send_json(404, {"error": f"找不到路徑：{path}"})
            return

        if action == "approve":
            result = self._handle_approve(run_id, body)
        else:
            result = self._handle_reject(run_id, body)

        approved_count = result.get("approved_count", 0)
        rejected_count = result.get("rejected_count", 0)
        if approved_count == 0 and rejected_count == 0:
            self._send_json(404, {"error": f"找不到待處理的 run 或項目：{run_id}"})
            return
        self._send_json(200, result)


def run(host: str = "127.0.0.1", port: int = 8765) -> HTTPServer:
    server = HTTPServer((host, port), _CommandCenterHandler)
    return server


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chairman Command Center API")
    parser.add_argument("--host", default="127.0.0.1", help="綁定主機（預設：127.0.0.1）")
    parser.add_argument("--port", type=int, default=8765, help="綁定埠號（預設：8765）")
    args = parser.parse_args()

    server = run(host=args.host, port=args.port)
    addr = server.server_address
    print(f"Command Center API listening on http://{addr[0]}:{addr[1]}")
    if args.host != "127.0.0.1":
        print("提示：非本機綁定，請確保只在信任的區域網路中使用。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
