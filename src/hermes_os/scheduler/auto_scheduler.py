"""Hermes OS — Auto Scheduler v1 core engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from hermes_os.scheduler.schemas import (
    AutoSchedulerConfig,
    FounderDecisionPriority,
    FounderDecisionTicket,
    SchedulerSource,
    SortedTaskQueue,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
    WatchdogSignal,
)


class AutoScheduler:
    """CoS Auto Task Scheduler v1 — deterministic, no external services."""

    def __init__(self, config: Optional[AutoSchedulerConfig] = None) -> None:
        self._config = config or AutoSchedulerConfig()
        self._candidates: Dict[str, TaskCandidate] = {}
        self._blocked_ids: set = set()
        self._waiting_founder_ids: set = set()
        self._audit: List[dict] = []
        self._now = datetime.utcnow()
        self._project_status_data: Dict[str, object] = {}
        self._contracts_index_data: Dict[str, object] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reload(
        self,
        project_status_path: Optional[Path] = None,
        contracts_index_path: Optional[Path] = None,
        watchdog_signals: Optional[List[WatchdogSignal]] = None,
        decision_queue_items: Optional[List[dict]] = None,
    ) -> None:
        """Re-hydrate scheduler state from sources."""
        self._now = datetime.utcnow()
        self._candidates = {}
        self._blocked_ids = set()
        self._waiting_founder_ids = set()
        self._project_status_data = {}
        self._contracts_index_data = {}

        if project_status_path:
            try:
                self._project_status_data = self._load_simple_yaml(project_status_path)
            except Exception:
                self._project_status_data = {}
        if contracts_index_path:
            try:
                self._contracts_index_data = self._load_simple_yaml(contracts_index_path)
            except Exception:
                self._contracts_index_data = {}

        self._ingest_project_status()
        self._ingest_contracts_index()
        self._ingest_watchdog(watchdog_signals or [])
        self._ingest_decision_queue(decision_queue_items or [])
        self._apply_drift()
        self._resolve_dependencies()
        self._enforce_guardrails()

        self._audit.append(
            {
                "action": "reload",
                "source": "auto_scheduler",
                "detail": f"candidates={len(self._candidates)}",
                "proposed_queue_length": len(self._candidates),
            }
        )

    def propose(self) -> SortedTaskQueue:
        """Return the current sorted, goal-formed task queue."""
        executable: List[TaskCandidate] = []
        blocked: List[TaskCandidate] = []
        waiting_founder: List[TaskCandidate] = []

        for c in sorted(self._candidates.values(), key=self._sort_key):
            if c.item_id in self._waiting_founder_ids:
                waiting_founder.append(c)
            elif c.item_id in self._blocked_ids:
                blocked.append(c)
            else:
                executable.append(c)

        founder_decisions = self._emit_founder_decisions()

        queue = SortedTaskQueue(
            proposed_at=self._now,
            executable=executable,
            blocked=blocked,
            waiting_founder=waiting_founder,
            founder_decisions=founder_decisions,
        )

        self._audit.append(
            {
                "action": "propose",
                "source": "auto_scheduler",
                "detail": (
                    f"executable={len(executable)} blocked={len(blocked)} "
                    f"waiting={len(waiting_founder)} decisions={len(founder_decisions)}"
                ),
                "proposed_queue_length": len(executable) + len(blocked) + len(waiting_founder),
            }
        )

        return queue

    def audit_log(self, limit: int = 20) -> List[dict]:
        """Return recent audit entries."""
        return list(self._audit[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ingest_project_status(self) -> None:
        blocked = self._project_status_data.get("blocked", False)
        if not blocked:
            return

        self._add_candidate(
            TaskCandidate(
                item_id="ps-unblock-1",
                title="解除 project-status blocked 狀態",
                priority=TaskPriority.P0,
                source=SchedulerSource.PROJECT_STATUS,
                status=TaskStatus.BLOCKED,
                metadata={"blocked_reason": str(self._project_status_data.get("blocked_reason", ""))},
            )
        )
        self._blocked_ids.add("ps-unblock-1")

    def _ingest_contracts_index(self) -> None:
        for contract in self._contracts_index_data.get("contracts", []):
            slug = str(contract.get("slug", ""))
            wuid = str(contract.get("id", ""))
            status = str(contract.get("status", ""))
            item_id = f"contract-{wuid or slug}"

            if status in ("signed", "in_progress"):
                priority = TaskPriority.P2 if status == "signed" else TaskPriority.P3
                self._add_candidate(
                    TaskCandidate(
                        item_id=item_id,
                        title=f"合約工作：{slug or wuid}",
                        priority=priority,
                        source=SchedulerSource.CONTRACTS_INDEX,
                        status=TaskStatus.QUEUED,
                        auto_start=(status == "signed"),
                        metadata={"contract_status": status},
                    )
                )
            elif status == "draft":
                self._add_candidate(
                    TaskCandidate(
                        item_id=item_id,
                        title=f"合約草稿待簽核：{slug or wuid}",
                        priority=TaskPriority.P1,
                        source=SchedulerSource.CONTRACTS_INDEX,
                        status=TaskStatus.WAITING_FOR_APPROVAL,
                        auto_start=False,
                        metadata={"contract_status": status},
                    )
                )
                if item_id not in self._waiting_founder_ids:
                    self._waiting_founder_ids.add(item_id)

    def _ingest_watchdog(self, signals: List[WatchdogSignal]) -> None:
        for signal in signals:
            candidate = TaskCandidate(
                item_id=signal.item_id,
                title=f"Watchdog 監測到停滯：{signal.item_id}",
                priority=TaskPriority.P2,
                source=SchedulerSource.WATCHDOG,
                status=TaskStatus.QUEUED,
                metadata={
                    "consecutive_idle_checks": signal.consecutive_idle_checks,
                    "health_status": signal.health_status,
                    "suggested_action": signal.suggested_action,
                },
            )
            self._add_candidate(candidate)

            if signal.consecutive_idle_checks >= self._config.watchdog_idle_block:
                if candidate.item_id not in self._waiting_founder_ids:
                    self._waiting_founder_ids.add(candidate.item_id)

    def _ingest_decision_queue(self, items: List[dict]) -> None:
        for idx, item in enumerate(items or []):
            ticket_id = str(item.get("ticket_id", f"dq-{idx}"))
            priority_raw = str(item.get("priority", "medium"))
            priority = {
                "critical": TaskPriority.P0,
                "high": TaskPriority.P1,
                "medium": TaskPriority.P2,
                "low": TaskPriority.P3,
            }.get(priority_raw, TaskPriority.P3)

            self._add_candidate(
                TaskCandidate(
                    item_id=ticket_id,
                    title=str(item.get("title", ticket_id)),
                    priority=priority,
                    source=SchedulerSource.FOUNDER_INBOX,
                    status=TaskStatus.WAITING_FOR_APPROVAL,
                    auto_start=False,
                    metadata={"decision_queue": True},
                )
            )
            if ticket_id not in self._waiting_founder_ids:
                self._waiting_founder_ids.add(ticket_id)

    def _add_candidate(self, candidate: TaskCandidate) -> None:
        if candidate.item_id in self._candidates:
            existing = self._candidates[candidate.item_id]
            if candidate.priority.value > existing.priority.value:
                self._candidates[candidate.item_id] = TaskCandidate(
                    **{
                        **existing.__dict__,
                        "priority": candidate.priority,
                        "source": candidate.source,
                        "updated_at": self._now,
                    }
                )
        else:
            self._candidates[candidate.item_id] = candidate

    def _apply_drift(self) -> None:
        drift_delta = timedelta(hours=self._config.drift_threshold_hours)
        for c in self._candidates.values():
            age = self._now - c.updated_at
            if age >= drift_delta * (c.drift_count + 1):
                c.__dict__["drift_count"] = c.drift_count + 1
                c.__dict__["priority"] = self._drift_priority(c.priority)
                c.__dict__["updated_at"] = self._now

    def _drift_priority(self, priority: TaskPriority) -> TaskPriority:
        order = [TaskPriority.P3, TaskPriority.P2, TaskPriority.P1, TaskPriority.P0]
        idx = order.index(priority)
        return order[min(len(order) - 1, idx + 1)]

    def _resolve_dependencies(self) -> None:
        for c in self._candidates.values():
            if not c.depends_on:
                continue
            unresolved = [d for d in c.depends_on if d not in self._candidates]
            if unresolved and c.item_id not in self._blocked_ids:
                self._blocked_ids.add(c.item_id)

    def _enforce_guardrails(self) -> None:
        # SG2: P0/P1 不得自動可執行（即便 auto_start=True）
        for c in self._candidates.values():
            if c.priority in (TaskPriority.P0, TaskPriority.P1):
                c.__dict__["auto_start"] = False

        # SG3: 若已滿，不可建議新的 executable；轉 waiting_founder
        executable_count = sum(
            1
            for c in self._candidates.values()
            if c.item_id not in self._blocked_ids
            and c.item_id not in self._waiting_founder_ids
            and c.status != TaskStatus.PAUSED
            and c.priority in (TaskPriority.P2, TaskPriority.P3)
        )
        if executable_count > self._config.max_concurrent:
            for c in self._candidates.values():
                if (
                    c.priority in (TaskPriority.P2, TaskPriority.P3)
                    and c.item_id not in self._blocked_ids
                    and c.item_id not in self._waiting_founder_ids
                    and c.status != TaskStatus.PAUSED
                ):
                    self._waiting_founder_ids.add(c.item_id)
                    break

    def _emit_founder_decisions(self) -> List[FounderDecisionTicket]:
        tickets: List[FounderDecisionTicket] = []

        for item_id in self._blocked_ids:
            c = self._candidates.get(item_id)
            if c is None:
                continue
            tickets.append(
                FounderDecisionTicket(
                    ticket_id=f"ticket-{item_id}-{self._now.strftime('%Y%m%d%H%M')}",
                    priority=FounderDecisionPriority(
                        {
                            TaskPriority.P0: "critical",
                            TaskPriority.P1: "high",
                            TaskPriority.P2: "medium",
                            TaskPriority.P3: "low",
                        }[c.priority]
                    ),
                    source=c.source,
                    title=f"阻塞處理事項：{c.title}",
                    summary="因相依未完成或外部條件不足而阻塞，請 Founder 確認處理方式。",
                    blocking_item_id=item_id,
                    options=["手動解除", "重新指派", "暫停並等待"],
                )
            )

        return tickets

    def _sort_key(self, candidate: TaskCandidate):
        """Sort key: priority ASC (P0 first), then source priority, then created_at."""
        priority_order = {
            TaskPriority.P0: 0,
            TaskPriority.P1: 1,
            TaskPriority.P2: 2,
            TaskPriority.P3: 3,
        }
        source_order = {
            SchedulerSource.PROJECT_STATUS: 0,
            SchedulerSource.CONTRACTS_INDEX: 1,
            SchedulerSource.RUNS: 2,
            SchedulerSource.WATCHDOG: 3,
            SchedulerSource.FOUNDER_INBOX: 4,
            SchedulerSource.PACKAGES: 5,
        }
        return (
            priority_order[candidate.priority],
            source_order.get(candidate.source, 9),
            candidate.created_at,
        )

    @staticmethod
    def _load_simple_yaml(path: Path) -> Dict[str, object]:
        """Minimal YAML loader for the SSOT files we consume."""
        text = path.read_text(encoding="utf-8")
        filename = path.name.lower()

        if filename == "contracts-index.yaml":
            return AutoScheduler._load_contracts_index(text)
        if filename == "project-status.yaml":
            return AutoScheduler._load_project_status(text)
        # Generic fallback: only top-level scalars
        data: Dict[str, object] = {}
        for raw_line in text.splitlines():
            if not raw_line.strip() or raw_line.strip().startswith("#"):
                continue
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.lower() in ("null", "~", ""):
                value = None
            else:
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
            data[key] = value
        return data

    @staticmethod
    def _load_contracts_index(text: str) -> Dict[str, object]:
        contracts: List[dict] = []
        current: Optional[dict] = None
        in_contracts = False
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped == "contracts:":
                in_contracts = True
                continue
            if not in_contracts:
                continue
            if stripped.startswith("-"):
                if current is not None:
                    contracts.append(current)
                current = {}
                # handle "- id: wu-001"
                rest = stripped[1:].strip()
                if rest and ":" in rest:
                    k, _, v = rest.partition(":")
                    current[k.strip()] = v.strip().strip('"')
            elif current is not None and ":" in stripped:
                k, _, v = stripped.partition(":")
                current[k.strip()] = v.strip().strip('"')
        if current is not None:
            contracts.append(current)
        return {"contracts": contracts}

    @staticmethod
    def _load_project_status(text: str) -> Dict[str, object]:
        data: Dict[str, object] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            v = v.strip()
            if v.lower() == "true":
                data[k] = True
            elif v.lower() == "false":
                data[k] = False
            else:
                data[k] = v.strip('"') if v.startswith('"') and v.endswith('"') else v
        return data
