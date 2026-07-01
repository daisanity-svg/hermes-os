"""Hermes OS — CoS Operating Runtime v1.

Chief of Staff (CoS) Runtime：最小可用之持續開發循環調度器。
責任：
1. 從 backlog / next_tasks 挑選已批准、低風險（P2/P3）、屬於主線範圍的任務。
2. 將任務派給 Hermes（ProcessAdapter）執行。
3. 完成後更新 Run Journal 與 Chairman Progress Report。
4. 若無阻塞則自動接續下一個任務；遇高風險、失敗、Scope 變更、需 Founder 決策時停止並建立 FounderDecisionTicket。

狀態機：
- IDLE：初始狀態，無任務執行。
- PICKING：正在從候選清單挑選下一個可執行任務。
- EXECUTING：任務執行中。
- REPORTING：任務完成，正在寫入 Run Journal / Progress Report。
- BLOCKED：遇到阻塞或高風險，需 Founder 介入。
- STOPPED：循環結束（不論正常或異常）。
- ERROR：系統錯誤。

用法：
    python -m hermes_os.cos_runtime run-once
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hermes_os.continuous_loop import (
    ContinuousDevelopmentLoop,
    LoopState,
    LoopStepResult,
    StopReason,
)
from hermes_os.process_adapter import ProcessAdapter
from hermes_os.run_journal import RunJournal
from hermes_os.scheduler.auto_scheduler import AutoScheduler
from hermes_os.scheduler.schemas import (
    AutoSchedulerConfig,
    FounderDecisionPriority,
    FounderDecisionTicket,
    SchedulerSource,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
)


class CosState(str, Enum):
    IDLE = "idle"
    PICKING = "picking"
    EXECUTING = "executing"
    REPORTING = "reporting"
    BLOCKED = "blocked"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class CosReport:
    generated_at: str
    project_code: Optional[str]
    project_name: Optional[str]
    completed: List[Dict[str, Any]]
    in_progress: Optional[Dict[str, Any]]
    next_up: Optional[Dict[str, Any]]
    founder_tickets: List[Dict[str, Any]]
    stop_reason: str


class CosRuntime:
    """ADO OS CoS Operating Runtime v1 — 最小可用調度器。"""

    def __init__(
        self,
        next_tasks_path: Optional[Path] = None,
        storage_path: Optional[Path] = None,
        max_tasks_per_cycle: int = 2,
        adapter: Any = None,
        project_code: Optional[str] = None,
        project_name: Optional[str] = None,
        max_tasks_per_session: int = 10,
        stop_on_failure: bool = True,
        stop_on_founder_decision: bool = True,
    ) -> None:
        self._next_tasks_path = next_tasks_path or self._default_next_tasks_path()
        self._storage_path = storage_path or self._default_storage_path()
        self._max_tasks_per_cycle = max_tasks_per_cycle
        self._project_code = project_code
        self._project_name = project_name
        self._max_tasks_per_session = max_tasks_per_session
        self._stop_on_failure = stop_on_failure
        self._stop_on_founder_decision = stop_on_founder_decision

        self._adapter = adapter or ProcessAdapter()
        self._journal = RunJournal(storage_path=self._storage_path)
        self._scheduler = AutoScheduler(config=AutoSchedulerConfig(max_concurrent=10))
        self._loop = ContinuousDevelopmentLoop(
            adapter=self._adapter,
            journal=self._journal,
            scheduler=self._scheduler,
            max_tasks_per_cycle=self._max_tasks_per_cycle,
            project_code=self._project_code,
            project_name=self._project_name,
            tick_hook=self._on_tick,
        )

        self._state = CosState.IDLE
        self._idle_reason: Optional[str] = "尚未啟動"
        self._last_report: Optional[CosReport] = None
        self._heartbeat_path = self._default_heartbeat_path()
        self._write_heartbeat()
        self._seed_scheduler_from_next_tasks()

    # ------------------------------------------------------------------
    # 狀態 helpers
    # ------------------------------------------------------------------
    def _set_project(self, project_code: Optional[str], project_name: Optional[str]) -> None:
        self._project_code = project_code
        self._project_name = project_name
        self._loop._project_code = project_code
        self._loop._project_name = project_name

    def switch_project(self, project_code: Optional[str], project_name: Optional[str] = None) -> Dict[str, Any]:
        self._set_project(project_code, project_name)
        self._seed_scheduler_from_next_tasks()
        self._write_heartbeat()
        return {
            "schema_version": "cos-runtime/status/v1",
            "project": {
                "code": project_code or "",
                "name": project_name or "",
            },
            "operational_status": self._operational_status_locked(),
        }

    def _set_idle_reason(self, reason: str) -> None:
        self._state = CosState.IDLE
        self._idle_reason = reason

    # ------------------------------------------------------------------
    # Tick hook：每個任務 step 完成後執行
    # ------------------------------------------------------------------
    def _status_payload(self) -> Dict[str, Any]:
        from hermes_os.cos_runtime.schema import empty_status
        status = empty_status(project_code=self._project_code)
        operational_status = self._operational_status_locked()
        status.update(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "project": {
                    "code": self._project_code or "",
                    "name": self._project_name or "",
                },
                "cos_state": self._state.value,
                "operational_status": operational_status,
                "idle_reason": self._idle_reason,
                "needs_founder_intervention": operational_status == "waiting_founder",
                "next_suggestion": self._next_suggestion_locked(),
                "heartbeat": self._read_heartbeat(),
                "sources": {
                    "next_tasks_path": str(self._next_tasks_path),
                    "journal_path": str(self._journal.storage_path if hasattr(self._journal, "storage_path") else ""),
                    "founder_inbox_path": str(self._next_tasks_path.parent / "founder-inbox.yaml"),
                },
            }
        )
        return status

    def _on_tick(self, result: LoopStepResult) -> None:
        if result.status == "completed":
            scheduler = self._loop._scheduler
            scheduler._candidates.pop(result.task_item_id, None)
            scheduler._waiting_founder_ids.discard(result.task_item_id)
            scheduler._blocked_ids.discard(result.task_item_id)
            # 刷新 next_candidate 以便 progress report 顯示正確
            self._loop._next_candidate = self._loop._pick_next()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def _replenish_next_tasks(self) -> None:
        """若 next_tasks 已無候選工作，從多數來源補貨。"""
        try:
            data = self._load_next_tasks_yaml()
            tasks = data.get("tasks", [])
            queued = [t for t in tasks if str(t.get("status", "queued")).lower() not in ("completed",)]
            if queued:
                return
        except Exception:
            return

        root = self._default_project_root()
        existing_ids = {str(t.get("item_id", "")) for t in tasks}
        appended = 0
        new_tasks: List[Dict[str, Any]] = []

        # source 1: contracts-index
        new_tasks.extend(self._replenish_from_contracts_index(root, existing_ids))
        # source 2: run journal
        new_tasks.extend(self._replenish_from_journal(root, existing_ids))
        # source 3: decision-queue / inbox
        new_tasks.extend(self._replenish_from_founder_inbox(root, existing_ids))

        if not new_tasks:
            return

        for task in new_tasks[:5]:
            tasks.append(task)
        data["tasks"] = tasks
        try:
            self._next_tasks_path.parent.mkdir(parents=True, exist_ok=True)
            self._next_tasks_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _replenish_from_contracts_index(self, root: Path, existing_ids: set) -> List[Dict[str, Any]]:
        path = root / "docs" / "sso" / "contracts-index.yaml"
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8")
            index = yaml.safe_load(text) or {}
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for contract in index.get("contracts", []):
            cid = str(contract.get("id", ""))
            slug = str(contract.get("slug", ""))
            if not cid and not slug:
                continue
            item_id = f"contract-{cid or slug}"
            if item_id in existing_ids:
                continue
            status = str(contract.get("status", "")).lower()
            if status not in ("signed", "in_progress", "draft"):
                continue
            out.append(
                {
                    "item_id": item_id,
                    "title": f"合約工作：{slug or cid}",
                    "priority": "P2" if status == "signed" else "P1",
                    "source": "contracts-index",
                    "status": "queued" if status == "signed" else "waiting_for_approval",
                    "auto_start": status == "signed",
                    "depends_on": [],
                    "metadata": {"contract_status": status},
                }
            )
            existing_ids.add(item_id)
        return out

    def _replenish_from_journal(self, root: Path, existing_ids: set) -> List[Dict[str, Any]]:
        journals = [
            root / "docs" / "sso" / "run-journal.json",
            root / ".hermes" / "cos" / "run-journal.json",
        ]
        out: List[Dict[str, Any]] = []
        seen_run_ids = set()
        for path in journals:
            if not path.exists():
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            entries = data.get("entries", []) if isinstance(data, dict) else []
            for raw in entries:
                run_id = str(raw.get("run_id", ""))
                if not run_id or run_id in seen_run_ids:
                    continue
                seen_run_ids.add(run_id)
                status = str(raw.get("status", "")).lower()
                if status in ("needs_founder_decision", "failed"):
                    item_id = f"followup-{run_id}"
                    if item_id in existing_ids:
                        continue
                    out.append(
                        {
                            "item_id": item_id,
                            "title": f"Run 後續處置：{raw.get('task_name', run_id)}",
                            "priority": "P2",
                            "source": "runs",
                            "status": "queued",
                            "auto_start": True,
                            "depends_on": [],
                            "metadata": {
                                "run_id": run_id,
                                "run_status": status,
                                "reason": raw.get("error") or raw.get("next_action") or "",
                            },
                        }
                    )
                    existing_ids.add(item_id)
        return out

    def _replenish_from_founder_inbox(self, root: Path, existing_ids: set) -> List[Dict[str, Any]]:
        path = root / ".hermes" / "cos" / "founder-inbox.yaml"
        if not path.exists():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for idx, ticket in enumerate(data.get("tickets", []) or [], start=1):
            raw_id = ticket.get("ticket_id") or ticket.get("id") or f"inbox-{idx}"
            item_id = f"inbox-{raw_id}"
            if item_id in existing_ids:
                continue
            status = str(ticket.get("status", "pending")).lower()
            if status not in ("pending", "open"):
                continue
            out.append(
                {
                    "item_id": item_id,
                    "title": ticket.get("title", str(raw_id)),
                    "priority": "P2",
                    "source": "founder-inbox",
                    "status": "waiting_for_approval",
                    "auto_start": False,
                    "depends_on": [],
                    "metadata": {"ticket_id": str(raw_id)},
                }
            )
            existing_ids.add(item_id)
        return out

    @staticmethod
    def _default_project_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def run_once(self) -> Dict[str, Any]:
        """執行一個 cycle（最多 max_tasks_per_cycle 個任務）。"""
        self._state = CosState.PICKING
        try:
            self._replenish_next_tasks()
            self._seed_scheduler_from_next_tasks()
            self._state = CosState.EXECUTING
            status = self._loop.start()
            self._state = CosState.REPORTING
            self._last_report = self._build_report()
            self._write_progress_report(self._last_report)
            self._mark_completed_in_next_tasks()
            # 决定最終狀態
            stop_reason = status.get("stop_reason", "none")
            if stop_reason == StopReason.FOUNDER_DECISION_REQUIRED.value:
                self._state = CosState.BLOCKED
                self._idle_reason = "等待 Founder 決策後才可繼續"
            elif stop_reason == StopReason.MAX_FAILURES.value:
                self._state = CosState.BLOCKED
                self._idle_reason = "連續失敗達上限，等待 Founder 確認"
            elif stop_reason == StopReason.NO_TASKS.value:
                self._state = CosState.STOPPED
                self._idle_reason = "目前無安全任務可執行"
            elif stop_reason == StopReason.CIRCUIT_OPEN.value:
                self._state = CosState.BLOCKED
                self._idle_reason = "熔斷器開啟，等待系統恢復"
            else:
                self._state = CosState.STOPPED
                self._idle_reason = "本輪 cycle 完成，等待下一輪触发"
            self._write_heartbeat()
            return self._compose_result(status)
        except Exception as exc:  # noqa: BLE001
            self._state = CosState.ERROR
            self._write_heartbeat()
            payload = self._to_v1_envelope()
            payload.update(
                {
                    "state": self._state.value,
                    "error": str(exc),
                }
            )
            return payload

    def daemon_run(
        self,
        interval: int = 60,
        max_tasks_per_session: Optional[int] = None,
        stop_on_failure: Optional[bool] = None,
        stop_on_founder_decision: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """持續循環調度：每個 cycle 完成後 sleep interval 秒再接續下一個，直到停止條件觸發。"""
        max_tasks = max_tasks_per_session if max_tasks_per_session is not None else self._max_tasks_per_session
        stop_failure = stop_on_failure if stop_on_failure is not None else self._stop_on_failure
        stop_founder = stop_on_founder_decision if stop_on_founder_decision is not None else self._stop_on_founder_decision

        total_executed = 0
        session_reports: List[Dict[str, Any]] = []
        founder_tickets: List[Dict[str, Any]] = []
        final_status = "none"

        try:
            while True:
                self._set_idle_reason("等待 cycle 間隔後接續")
                cycle_result = self.run_once()
                session_reports.append(cycle_result)
                completed_count = len(cycle_result.get("report", {}).get("completed", []))
                total_executed += completed_count

                loop_info = cycle_result.get("loop", {})
                stop_reason = loop_info.get("stop_reason", "none")
                cycle_founder_tickets = (cycle_result.get("report") or {}).get("founder_tickets", []) or []
                founder_tickets.extend(cycle_founder_tickets)
                final_status = stop_reason

                # 停止條件：本輪任務數達 session 上限
                if total_executed >= max_tasks:
                    final_status = final_status if final_status != "none" else "max_tasks_per_session"
                    break

                # 停止條件：Founder 決策
                if stop_founder and stop_reason == StopReason.FOUNDER_DECISION_REQUIRED.value:
                    self._write_founder_inbox(cycle_result)
                    final_status = "founder_decision_required"
                    break

                # 停止條件：失敗
                if stop_failure and stop_reason == StopReason.MAX_FAILURES.value:
                    final_status = "max_failures"
                    break

                # 停止條件：無任務
                if stop_reason == StopReason.NO_TASKS.value:
                    final_status = "no_tasks"
                    break

                time.sleep(interval)

            self._last_report = self._build_session_report(
                session_reports=session_reports,
                founder_tickets=founder_tickets,
                stop_reason=final_status,
                total_executed=total_executed,
            )
            self._write_progress_report(self._last_report)
            composed = self._compose_result({
                "stop_reason": final_status,
                "completed_count": total_executed,
                "founder_tickets_count": len(founder_tickets),
            })
            composed["session"]["reports"] = session_reports
            composed["session"]["founder_tickets"] = founder_tickets
            return composed
        except Exception as exc:  # noqa: BLE001
            self._state = CosState.ERROR
            payload = self._to_v1_envelope()
            payload.update(
                {
                    "state": self._state.value,
                    "session": {
                        "total_executed": total_executed,
                        "max_tasks_per_session": self._max_tasks_per_session,
                        "stop_reason": f"error: {exc}",
                        "reports": [],
                        "founder_tickets": founder_tickets,
                    },
                    "founder_tickets": founder_tickets,
                    "error": str(exc),
                }
            )
            return payload

    def status(self) -> Dict[str, Any]:
        with self._loop._lock:
            loop_status = self._loop._status_locked()
        payload = self._status_payload()
        operational_status = self._operational_status_locked(loop_status.get("stop_reason"))
        payload.update(
            {
                "state": self._state.value,
                "session": {
                    "total_executed": getattr(self._loop, "_session_executed_count", 0),
                    "max_tasks_per_session": self._max_tasks_per_session,
                    "stop_reason": loop_status.get("stop_reason", "none"),
                    "reports": [],
                    "founder_tickets": [],
                },
                "operational_status": operational_status,
                "project_code": payload["project"]["code"],
                "project_name": payload["project"]["name"],
                "max_tasks_per_cycle": self._max_tasks_per_cycle,
                "loop": loop_status,
                "last_report": self._report_to_dict(self._last_report),
                "current_cycle": {"in_progress": loop_status.get("current_task") or {}},
                "report": self._report_to_dict(self._last_report),
                "progress": self._report_to_dict(self._last_report),
                "cos_runtime": self._to_v1_envelope(),
            }
        )
        return payload

    def _operational_status_locked(self, loop_stop_reason: Optional[str] = None) -> str:
        if self._state == CosState.ERROR:
            return "error"
        if self._state in (CosState.PICKING, CosState.EXECUTING, CosState.REPORTING):
            return "running"
        if self._state == CosState.BLOCKED:
            if loop_stop_reason == StopReason.FOUNDER_DECISION_REQUIRED.value:
                return "waiting_founder"
            return "blocked"
        if self._state in (CosState.IDLE, CosState.STOPPED):
            return "idle"
        return "unknown"

    def _next_suggestion_locked(self) -> Optional[str]:
        operational = self._operational_status_locked()
        if operational == "waiting_founder":
            return self._idle_reason or "等待 Founder 決策後再繼續"
        if operational == "blocked":
            return "系統阻塞，需 Founder 介入解除"
        if operational == "error":
            return "系統錯誤，需檢查 Run Journal 與 Recovery"
        if operational == "running":
            return "正在執行任務，完成後自動驗收並接續下一項"
        return "等待 Founder 下達新目標或手動觸發 cycle"

    def progress(self) -> Dict[str, Any]:
        if self._last_report is None:
            self._last_report = self._build_report()
        return self._report_to_dict(self._last_report)

    def list_next_tasks(self) -> List[Dict[str, Any]]:
        try:
            data = self._load_next_tasks_yaml()
            return data.get("tasks", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _seed_scheduler_from_next_tasks(self) -> None:
        data = self._load_next_tasks_yaml()
        tasks = data.get("tasks", [])
        if not tasks:
            return

        # 覆寫 config
        raw_max = data.get("max_tasks_per_cycle")
        if raw_max is not None:
            try:
                self._max_tasks_per_cycle = int(raw_max)
                self._loop._max_tasks_per_cycle = self._max_tasks_per_cycle
            except (TypeError, ValueError):
                pass

        raw_project_code = data.get("project_code")
        if raw_project_code and not self._project_code:
            self._project_code = str(raw_project_code)
            self._loop._project_code = self._project_code
        raw_project_name = data.get("project_name")
        if raw_project_name and not self._project_name:
            self._project_name = str(raw_project_name)
            self._loop._project_name = self._project_name

        self._scheduler = AutoScheduler(config=AutoSchedulerConfig(max_concurrent=10))
        self._loop._scheduler = self._scheduler

        for task in tasks:
            item_id = str(task.get("item_id", ""))
            if not item_id:
                continue
            title = str(task.get("title", item_id))
            priority_raw = str(task.get("priority", "P3"))
            try:
                priority = TaskPriority(priority_raw)
            except ValueError:
                priority = TaskPriority.P3
            source_raw = str(task.get("source", "next-tasks"))
            try:
                source = SchedulerSource(source_raw)
            except ValueError:
                source = SchedulerSource.PACKAGES
            status_raw = str(task.get("status", "queued"))
            try:
                status = TaskStatus(status_raw)
            except ValueError:
                status = TaskStatus.QUEUED
            if status == TaskStatus.COMPLETED:
                continue
            auto_start = bool(task.get("auto_start", True))
            metadata = task.get("metadata", {}) or {}

            self._scheduler._candidates[item_id] = TaskCandidate(
                item_id=item_id,
                title=title,
                priority=priority,
                source=source,
                status=status,
                auto_start=auto_start,
                metadata=metadata,
            )
        self._scheduler._enforce_guardrails()
        # 避免 continuous_loop 每次 step 都呼叫 reload() 把候選任務清空
        self._scheduler.reload = lambda *a, **k: None

    def _mark_completed_in_next_tasks(self) -> None:
        try:
            data = self._load_next_tasks_yaml()
            tasks = data.get("tasks", [])
            completed_ids = {r["task_item_id"] for r in getattr(self._loop, "_completed_runs", [])}
            if not completed_ids:
                return
            changed = False
            for task in tasks:
                item_id = str(task.get("item_id", ""))
                if item_id in completed_ids and task.get("status") != "completed":
                    task["status"] = "completed"
                    changed = True
            if changed:
                import yaml
                self._next_tasks_path.write_text(
                    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
        except Exception:
            pass

    def _build_report(self) -> CosReport:
        with self._loop._lock:
            progress = self._loop._progress_locked()
        return CosReport(
            generated_at=progress.get("generated_at", datetime.now(timezone.utc).isoformat()),
            project_code=progress.get("project_code", self._project_code),
            project_name=progress.get("project_name", self._project_name),
            completed=progress.get("已完成", []),
            in_progress=progress.get("進行中"),
            next_up=progress.get("下一步"),
            founder_tickets=progress.get("需要_Founder_介入", []),
            stop_reason=progress.get("stop_reason", "none"),
        )

    def _write_progress_report(self, report: CosReport) -> None:
        try:
            base = self._next_tasks_path.parent / "progress-reports"
            base.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            path = base / f"{ts}.md"
            lines = [
                f"# Chairman Progress Report — {report.project_code or 'ado-os'}",
                "",
                f"> generated_at: {report.generated_at}",
                f"> project_code: {report.project_code}",
                f"> project_name: {report.project_name}",
                "",
                "## 執行摘要",
                f"本輪 cycle 完成 {len(report.completed)} 個任務。",
                f"停止原因：{report.stop_reason}。",
                "",
                "## 已完成",
            ]
            for item in reversed(report.completed):
                lines.append(
                    f"- [完成] {item.get('task', '未知')} "
                    f"（run_id: {item.get('run_id', '-')} — {item.get('status', '-')}）"
                )
            if not report.completed:
                lines.append("- （無）")

            lines.append("")
            lines.append("## 進行中")
            ip = report.in_progress
            if ip:
                lines.append(f"- [執行中] {ip.get('task', '-')} （step: {ip.get('step_id', '-')}）")
            else:
                lines.append("- （無）")

            lines.append("")
            lines.append("## 下一步")
            nxt = report.next_up
            if nxt:
                lines.append(f"- [待命] {nxt.get('title', '-')} （item_id: {nxt.get('item_id', '-')}）")
            else:
                lines.append("- （無）")

            lines.append("")
            lines.append("## 風險")
            risk_items = []
            for c in report.completed:
                err = c.get("error")
                if err:
                    risk_items.append(f"- {c.get('task')}: {err}")
            if report.founder_tickets:
                risk_items.append("- 需要 Founder 介入的決策事項：")
                for t in report.founder_tickets:
                    risk_items.append(f"  - {t.get('title', t.get('ticket_id', '-'))}")
            if risk_items:
                lines.extend(risk_items)
            else:
                lines.append("- （無顯著風險）")

            lines.append("")
            lines.append("## 需要 Founder 介入")
            if report.founder_tickets:
                for t in report.founder_tickets:
                    lines.append(
                        f"- [{t.get('priority', '-')}] {t.get('title', '-')} "
                        f"（{t.get('summary', '')}）"
                    )
            else:
                lines.append("- （無）")

            lines.append("")
            lines.append("---")
            lines.append("*Generated by CoS Agent | {timestamp}*".format(timestamp=datetime.now(timezone.utc).isoformat()))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _compose_result(self, loop_status: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cos_runtime": self._to_v1_envelope(),
            "schema_version": "cos-runtime/status/v1",
            "state": self._state.value,
            "session": {
                "total_executed": loop_status.get("completed_count", 0),
                "max_tasks_per_session": self._max_tasks_per_session,
                "stop_reason": loop_status.get("stop_reason", "none"),
                "reports": loop_status.get("reports", []),
                "founder_tickets": loop_status.get("founder_tickets", []),
            },
            "report": self._report_to_dict(self._last_report),
            "progress": self._report_to_dict(self._last_report),
            "loop": loop_status,
        }

    def _to_v1_envelope(self) -> Dict[str, Any]:
        return self._status_payload()

    def _report_to_dict(self, report: Optional[CosReport]) -> Dict[str, Any]:
        if report is None:
            return {}

        return {
            "generated_at": report.generated_at,
            "project_code": report.project_code,
            "project_name": report.project_name,
            "completed": report.completed,
            "in_progress": report.in_progress,
            "next_up": report.next_up,
            "founder_tickets": report.founder_tickets,
            "stop_reason": report.stop_reason,
        }

    def _build_session_report(
        self,
        session_reports: List[Dict[str, Any]],
        founder_tickets: List[Dict[str, Any]],
        stop_reason: str,
        total_executed: int,
    ) -> CosReport:
        all_completed: List[Dict[str, Any]] = []
        in_progress: Optional[Dict[str, Any]] = None
        next_up: Optional[Dict[str, Any]] = None
        project_code = self._project_code
        project_name = self._project_name

        for cycle in session_reports:
            report = cycle.get("report") or {}
            all_completed.extend(report.get("completed", []))
            if in_progress is None:
                in_progress = report.get("in_progress")
            if next_up is None:
                next_up = report.get("next_up")
            if project_code is None and report.get("project_code"):
                project_code = report["project_code"]
            if project_name is None and report.get("project_name"):
                project_name = report["project_name"]

        return CosReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            project_code=project_code,
            project_name=project_name,
            completed=all_completed,
            in_progress=in_progress,
            next_up=next_up,
            founder_tickets=founder_tickets,
            stop_reason=stop_reason,
        )

    def _write_founder_inbox(self, cycle_result: Dict[str, Any]) -> None:
        try:
            base = self._next_tasks_path.parent / "founder-inbox.yaml"
            existing: Dict[str, Any] = {}
            if base.exists():
                existing = yaml.safe_load(base.read_text(encoding="utf-8")) or {}
            existing.setdefault("tickets", [])

            tickets = (cycle_result.get("report") or {}).get("founder_tickets", []) or []
            for ticket in tickets:
                entry = dict(ticket)
                entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                entry.setdefault("session_stop_reason", "founder_decision_required")
                existing["tickets"].append(entry)

            base.write_text(
                yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------
    def _load_next_tasks_yaml(self) -> Dict[str, Any]:
        import yaml

        path = self._next_tasks_path
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _default_next_tasks_path() -> Path:
        return Path(__file__).resolve().parents[3] / ".hermes" / "cos" / "next_tasks.yaml"

    @staticmethod
    def _default_storage_path() -> Path:
        return Path(__file__).resolve().parents[2] / "docs" / "sso" / "run-journal.json"

    @staticmethod
    def _default_heartbeat_path() -> Path:
        return Path(__file__).resolve().parents[3] / ".hermes" / "cos" / "heartbeat.json"

    def _write_heartbeat(self) -> None:
        try:
            path = self._heartbeat_path
            path.parent.mkdir(parents=True, exist_ok=True)
            stop_reason = None
            if hasattr(self._loop, "_status_locked"):
                try:
                    stop_reason = self._loop._status_locked().get("stop_reason")
                except Exception:
                    stop_reason = None
            op = self._operational_status_locked(stop_reason)
            payload = {
                "pid": os.getpid(),
                "operational_status": op,
                "last_heartbeat": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "idle_reason": self._idle_reason,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _read_heartbeat(self) -> Dict[str, Any]:
        try:
            path = self._heartbeat_path
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
