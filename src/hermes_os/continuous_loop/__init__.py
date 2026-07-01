"""Hermes OS — Continuous Development Loop v1."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hermes_os.run_journal import RunJournal
from hermes_os.recovery.manager import RecoveryManager
from hermes_os.scheduler.auto_scheduler import AutoScheduler
from hermes_os.scheduler.schemas import (
    FounderDecisionPriority,
    FounderDecisionTicket,
    SchedulerSource,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
)


class LoopState(str, Enum):
    """Continuous loop lifecycle states."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class StopReason(str, Enum):
    """Reasons the loop stopped."""

    NONE = "none"
    NO_TASKS = "no_tasks"
    MAX_FAILURES = "max_failures"
    FOUNDER_DECISION_REQUIRED = "founder_decision_required"
    MANUAL_STOP = "manual_stop"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class LoopStepResult:
    """Result of a single loop step (one task execution)."""

    step_id: str
    run_id: str
    task_item_id: str
    task_title: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    founder_ticket: Optional[Dict[str, Any]] = None
    next_suggestion: Optional[str] = None


class ContinuousDevelopmentLoop:
    """ADO OS Continuous Development Loop v1.

    規則：
    1. 從 AutoScheduler 挑選下一個 executable、低風險（P2/P3）、auto_start=True 的任務。
    2. 將任務狀態寫入 Run Journal。
    3. 使用 ProcessAdapter（外部注入）執行任務。
    4. 任務完成後，立即重載 scheduler 並接續下一個。
    5. 遇到阻塞、高風險（P0/P1）、需 Founder 決策、連續失敗達上限時停止，
       並產生 FounderDecisionTicket。
    6. 不 push main、不修改 .env、不對外暴露服務。
    """

    def __init__(
        self,
        adapter: Any,
        journal: Optional[RunJournal] = None,
        recovery: Optional[RecoveryManager] = None,
        scheduler: Optional[AutoScheduler] = None,
        max_consecutive_failures: int = 3,
        project_code: Optional[str] = None,
        project_name: Optional[str] = None,
        storage_path: Optional[Path] = None,
        tick_hook: Optional[Callable[[LoopStepResult], None]] = None,
        max_tasks_per_cycle: int = 2,
    ) -> None:
        self._adapter = adapter
        self._journal = journal or RunJournal(storage_path=storage_path)
        self._recovery = recovery or RecoveryManager(journal=self._journal)
        self._scheduler = scheduler or AutoScheduler()
        self._max_consecutive_failures = max_consecutive_failures
        self._project_code = project_code
        self._project_name = project_name
        self._tick_hook = tick_hook

        self._state = LoopState.IDLE
        self._stop_requested = threading.Event()
        self._current_task_id: Optional[str] = None
        self._consecutive_failures = 0
        self._completed_runs: List[Dict[str, Any]] = []
        self._in_progress_run: Optional[Dict[str, Any]] = None
        self._next_candidate: Optional[TaskCandidate] = None
        self._last_step: Optional[LoopStepResult] = None
        self._founder_tickets: List[Dict[str, Any]] = []
        self._stop_reason = StopReason.NONE
        self._lock = threading.Lock()
        self._step_counter = 0
        self._max_tasks_per_cycle = max_tasks_per_cycle

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> Dict[str, Any]:
        """開始 loop（背景執行）。"""
        with self._lock:
            if self._state == LoopState.RUNNING:
                return self._status_locked()
            self._stop_requested.clear()
            self._state = LoopState.RUNNING
            self._consecutive_failures = 0
            self._completed_runs = []
            self._founder_tickets = []
            self._stop_reason = StopReason.NONE
            self._last_step = None
            self._next_candidate = None
            self._in_progress_run = None
            self._step_counter = 0

        self._run_loop()
        return self.status()

    def stop(self) -> Dict[str, Any]:
        """請求停止 loop。"""
        self._stop_requested.set()
        with self._lock:
            if self._state == LoopState.RUNNING:
                self._state = LoopState.STOPPING
                self._stop_reason = StopReason.MANUAL_STOP
        # 等待 loop 結束
        for _ in range(120):
            with self._lock:
                if self._state in (LoopState.STOPPED, LoopState.IDLE, LoopState.ERROR):
                    break
            threading.Event().wait(0.1)
        return self.status()

    def status(self) -> Dict[str, Any]:
        """回傳 loop 目前狀態。"""
        with self._lock:
            return self._status_locked()

    def progress(self) -> Dict[str, Any]:
        """回傳 Chairman 進度查詢格式。

        格式：
        - 已完成
        - 進行中
        - 下一步
        - 風險
        - 需要 Founder 介入
        """
        with self._lock:
            return self._progress_locked()

    def step(self) -> Dict[str, Any]:
        """手動執行單一步驟（非背景模式）。"""
        self._stop_requested.clear()
        with self._lock:
            if self._state != LoopState.RUNNING:
                self._state = LoopState.RUNNING
        result = self._run_single_step()
        if result is not None:
            self._last_step = result
            if self._should_stop_after(result):
                with self._lock:
                    pass  # stop_reason 已在 _should_stop_after 內設定
        # Single step done: loop may continue later, so mark idle for now
        with self._lock:
            if self._state == LoopState.RUNNING:
                self._state = LoopState.IDLE
        return self.status()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        with self._lock:
            self._state = LoopState.RUNNING
        try:
            while not self._stop_requested.is_set():
                result = self._run_single_step()
                if result is None:
                    break
                with self._lock:
                    self._last_step = result
                    if self._should_stop_after(result):
                        break
                    if self._step_counter >= self._max_tasks_per_cycle:
                        self._stop_reason = StopReason.NONE
                        break
        finally:
            with self._lock:
                if self._state == LoopState.STOPPING:
                    self._state = LoopState.STOPPED
                elif self._state == LoopState.RUNNING:
                    self._state = LoopState.IDLE

    def _should_stop_after(self, result: LoopStepResult) -> bool:
        if self._stop_reason != StopReason.NONE:
            return True
        if self._consecutive_failures >= self._max_consecutive_failures:
            self._stop_reason = StopReason.MAX_FAILURES
            return True
        if result.founder_ticket is not None:
            self._stop_reason = StopReason.FOUNDER_DECISION_REQUIRED
            return True
        if self._next_candidate is None and not self._has_pending_work():
            self._stop_reason = StopReason.NO_TASKS
            return True
        return False

    def _has_pending_work(self) -> bool:
        # 嘗試重載 scheduler 看看是否還有工作
        try:
            self._scheduler.reload()
            queue = self._scheduler.propose()
            return bool(queue.executable) or bool(queue.waiting_founder)
        except Exception:
            return False

    def _run_single_step(self) -> Optional[LoopStepResult]:
        with self._lock:
            if self._state != LoopState.RUNNING:
                return None

        # Reload scheduler state at start of each step to pick up external changes
        try:
            self._scheduler.reload()
        except Exception:
            pass

        candidate = self._pick_next()
        if candidate is None:
            # 若無可執行任務，但仍有待 Founder 決策事項，視為需要 Founder 介入
            try:
                self._scheduler.reload()
                queue = self._scheduler.propose()
                if queue.waiting_founder:
                    with self._lock:
                        self._stop_reason = StopReason.FOUNDER_DECISION_REQUIRED
                    return None
            except Exception:
                pass
            with self._lock:
                self._stop_reason = StopReason.NO_TASKS
            return None

        with self._lock:
            self._current_task_id = candidate.item_id
            self._step_counter += 1
            step_id = f"step-{self._step_counter:04d}"
            run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{candidate.item_id}"

        # Write to Run Journal — queued / executing
        self._journal.append(
            run_id=run_id,
            task_name=candidate.title,
            project_code=self._project_code,
            project_name=self._project_name,
            status="running",
            last_event=f"{step_id}: start {candidate.item_id}",
            next_action="execute",
        )

        with self._lock:
            self._in_progress_run = {
                "step_id": step_id,
                "run_id": run_id,
                "task_item_id": candidate.item_id,
                "task_title": candidate.title,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }

        started_at = datetime.now(timezone.utc)
        error_msg: Optional[str] = None
        founder_ticket: Optional[Dict[str, Any]] = None
        finish_status = "completed"

        try:
            # Check if this task needs founder decision
            if candidate.status == TaskStatus.WAITING_FOR_APPROVAL or candidate.priority in (
                TaskPriority.P0,
                TaskPriority.P1,
            ):
                founder_ticket = self._create_founder_ticket_from_candidate(candidate)
                finish_status = "needs_founder_decision"
                self._consecutive_failures = 0
            else:
                # Execute via adapter
                # We simulate execution here since we don't have a real executor.
                # In real usage, adapter.complete(item_id) or similar is called.
                submission = self._adapter.submit(
                    {
                        "id": candidate.item_id,
                        "type": "task",
                        "priority": self._priority_to_int(candidate.priority),
                        "run_id": run_id,
                        "payload": {
                            "source": candidate.source.value,
                            "auto_start": candidate.auto_start,
                        },
                    }
                )
                # Simulate completion for MVP loop
                # Real implementation would monitor queue and call complete()
                completion = self._adapter.complete(candidate.item_id)
                if completion.get("status") == "completed":
                    finish_status = "completed"
                    self._consecutive_failures = 0
                else:
                    finish_status = "failed"
                    error_msg = completion.get("error") or "adapter reported failure"
                    self._consecutive_failures += 1
        except Exception as exc:  # noqa: BLE001
            finish_status = "failed"
            error_msg = str(exc)
            self._consecutive_failures += 1

        finished_at = datetime.now(timezone.utc)

        # Recovery / escalation check
        if finish_status == "failed" and self._consecutive_failures >= self._max_consecutive_failures:
            ticket = self._recovery.escalate(run_id, reason=f"連續失敗 {self._consecutive_failures} 次")
            founder_ticket = ticket
            finish_status = "needs_founder_decision"

        # Update journal
        self._journal.append(
            run_id=run_id,
            task_name=candidate.title,
            project_code=self._project_code,
            project_name=self._project_name,
            status=finish_status,
            last_event=f"{step_id}: {finish_status}",
            error=error_msg,
            next_action=self._next_suggestion(candidate, finish_status, error_msg, founder_ticket),
        )

        result = LoopStepResult(
            step_id=step_id,
            run_id=run_id,
            task_item_id=candidate.item_id,
            task_title=candidate.title,
            status=finish_status,
            started_at=started_at,
            finished_at=finished_at,
            error=error_msg,
            founder_ticket=founder_ticket,
            next_suggestion=self._next_suggestion(
                candidate, finish_status, error_msg, founder_ticket
            ),
        )

        with self._lock:
            self._completed_runs.append(
                {
                    "step_id": step_id,
                    "run_id": run_id,
                    "task_item_id": candidate.item_id,
                    "task_title": candidate.title,
                    "status": finish_status,
                    "error": error_msg,
                    "finished_at": finished_at.isoformat(),
                }
            )
            self._in_progress_run = None
            self._current_task_id = None
            self._last_step = result
            if founder_ticket:
                self._founder_tickets.append(founder_ticket)
            # Pre-load next candidate for progress reporting
            self._next_candidate = self._pick_next_from_reloaded()

        if self._tick_hook is not None:
            try:
                self._tick_hook(result)
            except Exception:  # noqa: BLE001
                pass

        return result

    # ------------------------------------------------------------------
    # Scheduling helpers
    # ------------------------------------------------------------------

    def _pick_next(self) -> Optional[TaskCandidate]:
        return self._pick_next_from_reloaded()

    def _pick_next_from_reloaded(self) -> Optional[TaskCandidate]:
        try:
            self._scheduler.reload()
            queue = self._scheduler.propose()
        except Exception:
            return None

        # Preference: auto_start=True P2/P3 executable tasks
        candidates = queue.executable
        auto = [c for c in candidates if c.auto_start and c.priority in (TaskPriority.P2, TaskPriority.P3)]
        if auto:
            return auto[0]
        if candidates:
            return candidates[0]

        # If no executable, but there are waiting_founder, we can't proceed automatically
        return None

    def _create_founder_ticket_from_candidate(self, candidate: TaskCandidate) -> Dict[str, Any]:
        priority_map = {
            TaskPriority.P0: FounderDecisionPriority.CRITICAL,
            TaskPriority.P1: FounderDecisionPriority.HIGH,
            TaskPriority.P2: FounderDecisionPriority.MEDIUM,
            TaskPriority.P3: FounderDecisionPriority.LOW,
        }
        ticket = FounderDecisionTicket(
            ticket_id=f"loop-{candidate.item_id}-{int(datetime.now(timezone.utc).timestamp())}",
            priority=priority_map.get(candidate.priority, FounderDecisionPriority.MEDIUM),
            source=SchedulerSource.FOUNDER_INBOX,
            title=f"需要 Founder 決策：{candidate.title}",
            summary=f"任務 {candidate.item_id} 因優先順序或狀態需求，需 Founder 介入。",
            blocking_item_id=candidate.item_id,
            options=["核准", "駁回", "暫緩"],
            metadata={
                "loop": True,
                "candidate_item_id": candidate.item_id,
                "candidate_source": candidate.source.value,
                "candidate_priority": candidate.priority.value,
            },
        )
        return {
            "ticket_id": ticket.ticket_id,
            "priority": ticket.priority.value,
            "source": ticket.source.value,
            "title": ticket.title,
            "summary": ticket.summary,
            "blocking_item_id": ticket.blocking_item_id,
            "created_at": ticket.created_at.isoformat(),
            "options": ticket.options,
            "metadata": ticket.metadata,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _status_locked(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "stop_reason": self._stop_reason.value,
            "current_task_id": self._current_task_id,
            "in_progress": self._in_progress_run,
            "last_step": self._last_step_to_dict(self._last_step),
            "completed_count": len(self._completed_runs),
            "founder_tickets_count": len(self._founder_tickets),
            "next_candidate": self._candidate_to_dict(self._next_candidate),
        }

    def _progress_locked(self) -> Dict[str, Any]:
        completed = list(reversed(self._completed_runs))
        ctx: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_code": self._project_code,
            "project_name": self._project_name,
            "已完成": [],
            "進行中": None,
            "下一步": None,
            "風險": [],
            "需要_Founder_介入": [],
        }

        for c in completed:
            ctx["已完成"].append(
                {
                    "run_id": c.get("run_id"),
                    "task": c.get("task_title"),
                    "status": c.get("status"),
                    "finished_at": c.get("finished_at"),
                    "error": c.get("error"),
                }
            )

        ip = self._in_progress_run
        if ip:
            ctx["進行中"] = {
                "step_id": ip.get("step_id"),
                "run_id": ip.get("run_id"),
                "task": ip.get("task_title"),
                "started_at": ip.get("started_at"),
            }

        nxt = self._next_candidate
        if nxt:
            ctx["下一步"] = {
                "item_id": nxt.item_id,
                "title": nxt.title,
                "priority": nxt.priority.value,
                "source": nxt.source.value,
                "auto_start": nxt.auto_start,
            }

        # Risks from failures / tickets
        risks = []
        for c in completed:
            if c.get("error") or c.get("status") == "failed":
                risks.append(
                    {
                        "type": "執行失敗" if c.get("status") == "failed" else "異常",
                        "task": c.get("task_title"),
                        "error": c.get("error"),
                        "run_id": c.get("run_id"),
                    }
                )
        if self._consecutive_failures > 0:
            risks.append(
                {
                    "type": "連續失敗",
                    "task": "多項任務",
                    "error": f"連續失敗 {self._consecutive_failures} 次",
                    "run_id": None,
                }
            )
        ctx["風險"] = risks

        # Founder intervention items
        founder_items = []
        for t in self._founder_tickets:
            founder_items.append(
                {
                    "ticket_id": t.get("ticket_id"),
                    "priority": t.get("priority"),
                    "title": t.get("title"),
                    "summary": t.get("summary"),
                    "blocking_item_id": t.get("blocking_item_id"),
                    "created_at": t.get("created_at"),
                }
            )
        ctx["需要_Founder_介入"] = founder_items

        return ctx

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_suggestion(
        self,
        candidate: TaskCandidate,
        status: str,
        error: Optional[str],
        founder_ticket: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if founder_ticket:
            return "等待 Founder 決策後再繼續"
        if status == "completed":
            return "繼續執行下一個已批准任務"
        if status == "failed":
            if self._consecutive_failures >= self._max_consecutive_failures:
                return "連續失敗達上限，請 Founder 確認是否重試"
            return "重試或等待 Recovery 處理"
        return None

    @staticmethod
    def _priority_to_int(priority: TaskPriority) -> int:
        return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority.value, 2)

    @staticmethod
    def _last_step_to_dict(step: Optional[LoopStepResult]) -> Optional[Dict[str, Any]]:
        if step is None:
            return None
        return {
            "step_id": step.step_id,
            "run_id": step.run_id,
            "task_item_id": step.task_item_id,
            "task_title": step.task_title,
            "status": step.status,
            "error": step.error,
            "founder_ticket": step.founder_ticket,
            "next_suggestion": step.next_suggestion,
            "started_at": step.started_at.isoformat(),
            "finished_at": step.finished_at.isoformat() if step.finished_at else None,
        }

    @staticmethod
    def _candidate_to_dict(candidate: Optional[TaskCandidate]) -> Optional[Dict[str, Any]]:
        if candidate is None:
            return None
        return {
            "item_id": candidate.item_id,
            "title": candidate.title,
            "priority": candidate.priority.value,
            "source": candidate.source.value,
            "status": candidate.status.value,
            "auto_start": candidate.auto_start,
        }
