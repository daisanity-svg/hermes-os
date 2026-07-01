"""Command Center Adapter — unify Executive Brief, Department Health, Decision Queue, Company Health via SignalRegistry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_os.org_learning.brief import signals_to_executive_brief_items
from hermes_os.org_learning.health import (
    DepartmentHealth,
    DepartmentHealthCalculator,
    health_to_signals,
)
from hermes_os.org_learning.providers import (
    DepartmentHealthSignalProvider,
    FinancialSnapshotProvider,
    OperationalRiskProvider,
    SignalRegistry,
    StrategicSignalDigestProvider,
)
from hermes_os.org_learning.signals import SignalCategory
from hermes_os.org_learning.decision_queue import (
    DecisionStatus,
    DecisionTicket,
    HumanDecisionQueue,
)
from hermes_os.scheduler.auto_scheduler import AutoScheduler
from hermes_os.scheduler.schemas import SortedTaskQueue
from hermes_os.run_journal import RunJournal
from hermes_os.recovery import RecoveryManager
from hermes_os.workflow_records import WorkflowRecords


class CommandCenterAdapter:
    """統一讀取 Command Center 所需資料，避免前端直接耦合 business module。"""

    def __init__(self, registry: Optional[SignalRegistry] = None) -> None:
        self.registry = registry or SignalRegistry()
        self._register_default_providers()
        self._workflow_records = WorkflowRecords()
        self._journal = RunJournal()
        self._recovery = RecoveryManager(journal=self._journal)
        self._inbox = HumanDecisionQueue()
        if not self._inbox.list_pending():
            self._inbox.enqueue(
                DecisionTicket(
                    ticket_id="dq-001",
                    title="Q3 行銷預算重新分配",
                    description="行銷部提案：將電視廣告預算轉為社群與差旅",
                    department="行銷",
                    status=DecisionStatus.PENDING,
                    submitter="行銷部",
                    estimated_processing_time="2 天",
                )
            )
            self._inbox.enqueue(
                DecisionTicket(
                    ticket_id="dq-002",
                    title="數學森林美術方向確認",
                    description="工程部與設計部對美術童書感程度有不同意見，需 Chairman 定調",
                    department="工程",
                    status=DecisionStatus.PENDING,
                    submitter="工程部",
                    estimated_processing_time="1 天",
                )
            )
        # Seed a demo running workflow
        if not self._workflow_records.list_running():
            self._workflow_records.start("wf-001", "item-001", metadata={"name": "數學 forest 美術審查"})

    def _register_default_providers(self) -> None:
        """註冊預設 providers；可被外部覆寫。"""
        self.registry.register(FinancialSnapshotProvider())
        self.registry.register(StrategicSignalDigestProvider())
        # Department health + decision queue 由對應方法動態提供

    def get_executive_brief(self) -> List[Dict[str, Any]]:
        """Executive Brief：從 signals 過濾高信賴或 Chairman 首要關注項目。"""
        signals = self.registry.fetch_all()
        brief_signals = signals_to_executive_brief_items(signals)
        return [self._signal_to_item(s) for s in brief_signals]

    def get_department_health(
        self,
        department: str = "engineering",
        metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """Department Visit：計算部門健康度並轉為 signals。"""
        calc = DepartmentHealthCalculator()
        metrics = metrics or self._default_department_metrics(department)
        health = calc.compute(department, metrics)
        signals = health_to_signals(health)
        return {
            "department": health.department,
            "overall_score": health.overall_score,
            "computed_at": health.computed_at.isoformat()
            if hasattr(health.computed_at, "isoformat")
            else str(health.computed_at),
            "signals": [self._signal_to_item(s) for s in signals],
        }

    def get_decision_queue_signals(
        self, pending_tickets: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Human Decision Queue：將 pending tickets 轉為 risk signals。"""
        provider = OperationalRiskProvider(pending_decision_tickets=pending_tickets)
        signals = provider.fetch_signals()
        return [self._signal_to_item(s) for s in signals]

    def get_company_health(self) -> Dict[str, Any]:
        """Company Health：以 signals 聚合雛形呈現。"""
        signals = self.registry.fetch_all()
        priority = [s for s in signals if s.priority_for_chairman]
        high_conf = [s for s in signals if s.confidence >= 0.85]

        dimension_scores: Dict[str, float] = {}
        for s in signals:
            if s.category.name == "OPERATIONAL" and s.sub_category == "department_health":
                # extract dimension from title
                title = s.title
                for dim in ["velocity", "quality", "stability", "alignment", "capacity"]:
                    if dim in title.lower():
                        dimension_scores[dim] = float(s.value or 0.0)
                        break

        return {
            "total_signals": len(signals),
            "priority_count": len(priority),
            "high_confidence_count": len(high_conf),
            "by_category": {
                cat.value: sum(1 for s in signals if s.category == cat)
                for cat in SignalCategory
            },
            "dimension_scores": dimension_scores,
            "priority_signals": [self._signal_to_item(s) for s in priority[:5]],
        }

    def get_overview(self) -> Dict[str, Any]:
        """總覽：一次取回所有區塊資料。"""
        brief = self.get_executive_brief()
        return {
            "executive_brief": brief,
            "last_brief_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if brief else None,
            "department_health": self.get_department_health(),
            "decision_queue": self.get_decision_queue_signals(),
            "company_health": self.get_company_health(),
        }

    def get_active_projects(self) -> Dict[str, Any]:
        """Active Projects：讀取 project-status.yaml 與 contracts-index.yaml，並附上每筆合約的最後 AI 更新時間。"""
        repo = Path(__file__).resolve().parents[3]
        project_path = repo / "docs" / "sso" / "project-status.yaml"
        contracts_path = repo / "docs" / "sso" / "contracts-index.yaml"
        project = {}
        contracts = {"contracts": []}
        try:
            project = AutoScheduler._load_simple_yaml(project_path)
        except Exception:
            pass
        try:
            contracts = AutoScheduler._load_simple_yaml(contracts_path)
        except Exception:
            pass

        # 根據 run journal 計算每筆合約/專案的最後 AI 更新時間
        enriched_contracts = []
        for c in contracts.get("contracts", []):
            item_id = c.get("slug") or c.get("id") or c.get("work_unit_id")
            last_ai_update = self._last_ai_update_for(item_id)
            enriched = dict(c)
            enriched["last_ai_update"] = last_ai_update
            enriched_contracts.append(enriched)

        return {
            "project": project,
            "contracts": enriched_contracts,
        }

    def _last_ai_update_for(self, item_id: Optional[str]) -> Optional[str]:
        if not item_id:
            return None
        # 從 run journal 找出與此 item_id 相關的最新 run
        journal = self._journal
        matches = []
        for entry in journal.list():
            if entry.task_name == item_id or item_id in (entry.project_code or ""):
                matches.append(entry)
        if not matches:
            return None
        latest = max(matches, key=lambda e: e.updated_at)
        return latest.updated_at.isoformat() if hasattr(latest.updated_at, "isoformat") else str(latest.updated_at)

    def get_active_workflows(self) -> Dict[str, Any]:
        """Active Workflows：目前執行中的 workflow 清單。"""
        running = self._workflow_records.list_running()
        return {
            "count": len(running),
            "workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "root_item_id": w.root_item_id,
                    "status": w.status,
                    "updated_at": w.updated_at,
                    "metadata": w.metadata,
                }
                for w in running
            ],
        }

    def get_runs_mirror(self) -> Dict[str, Any]:
        """Hermes Runs Mirror：目前與近期 run 狀態。"""
        runs = [
            {
                "run_id": entry.run_id,
                "status": entry.status,
                "updated_at": entry.updated_at.isoformat() if hasattr(entry.updated_at, "isoformat") else str(entry.updated_at),
            }
            for entry in self._journal.list()
        ]
        return {
            "count": len(runs),
            "runs": sorted(runs, key=lambda r: r.get("updated_at", ""), reverse=True),
        }

    def get_reliability_overview(self) -> Dict[str, Any]:
        """Reliability Overview：讀取 RunJournal 與 RecoveryManager 狀態。"""
        all_runs = self._journal.list()
        recoverable = self._recovery.list_recoverable()

        counts: Dict[str, int] = {
            "running": 0,
            "completed": 0,
            "failed": 0,
            "lost": 0,
            "recovering": 0,
            "needs_founder_decision": 0,
        }
        for entry in all_runs:
            status = entry.status
            if status in counts:
                counts[status] += 1

        recent_abnormal = []
        for run in recoverable[:5]:
            recent_abnormal.append(
                {
                    "run_id": run.run_id,
                    "project_code": run.project_code,
                    "project_name": run.project_name,
                    "task_name": run.task_name,
                    "status": run.current_status,
                    "recovery_status": run.recovery_status.value if hasattr(run.recovery_status, "value") else str(run.recovery_status),
                    "reason": run.reason,
                    "next_action": run.reason,
                    "updated_at": run.updated_at.isoformat() if hasattr(run.updated_at, "isoformat") else str(run.updated_at),
                }
            )

        founder_tickets = []
        for run in recoverable:
            if (run.recovery_status.value if hasattr(run.recovery_status, "value") else str(run.recovery_status)) == "needs_founder_decision":
                founder_tickets.append(
                    {
                        "run_id": run.run_id,
                        "project_code": run.project_code,
                        "project_name": run.project_name,
                        "task_name": run.task_name,
                        "reason": run.reason,
                        "retry_count": run.retry_count,
                    }
                )

        return {
            "counts": counts,
            "recent_abnormal": recent_abnormal,
            "founder_tickets": founder_tickets,
        }

    def get_scheduler_queue(self) -> Dict[str, Any]:
        """Auto Scheduler：SortedTaskQueue 結果。"""
        from dataclasses import asdict

        repo = Path(__file__).resolve().parents[3]
        scheduler = AutoScheduler()
        scheduler.reload(
            project_status_path=repo / "docs" / "sso" / "project-status.yaml",
            contracts_index_path=repo / "docs" / "sso" / "contracts-index.yaml",
        )
        queue = scheduler.propose()
        return asdict(queue)

    def get_founder_inbox(self) -> Dict[str, Any]:
        """Founder Inbox：待決策事項（Human Decision Queue）。"""
        pending = self._inbox.list_pending()
        return {
            "count": len(pending),
            "tickets": [
                {
                    "ticket_id": t.ticket_id,
                    "title": t.title,
                    "description": t.description,
                    "department": t.department,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    "created_at": t.created_at.isoformat()
                    if hasattr(t.created_at, "isoformat")
                    else str(t.created_at),
                    "submitter": t.submitter,
                    "estimated_processing_time": t.estimated_processing_time,
                }
                for t in pending
            ],
        }

    def get_package_timeline(self) -> Dict[str, Any]:
        """Package Timeline：讀取 packages-index.yaml。"""
        repo = Path(__file__).resolve().parents[3]
        index_path = repo / "docs" / "packages" / "packages-index.yaml"
        try:
            text = index_path.read_text(encoding="utf-8")
        except Exception:
            return {"generated_at": "", "packages": []}
        packages: List[Dict[str, str]] = []
        current: Optional[Dict[str, str]] = None
        in_packages = False
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped == "packages:":
                in_packages = True
                continue
            if not in_packages:
                continue
            if stripped.startswith("-"):
                if current is not None:
                    packages.append(current)
                current = {}
                rest = stripped[1:].strip()
                if rest and ":" in rest:
                    k, _, v = rest.partition(":")
                    current[k.strip()] = v.strip().strip('"')
            elif current is not None and ":" in stripped:
                k, _, v = stripped.partition(":")
                current[k.strip()] = v.strip().strip('"')
        if current is not None:
            packages.append(current)
        return {"generated_at": "", "packages": packages}

    @staticmethod
    def _signal_to_item(signal: Any) -> Dict[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "category": signal.category.value if hasattr(signal.category, "value") else str(signal.category),
            "sub_category": signal.sub_category,
            "title": signal.title,
            "summary": signal.summary,
            "value": signal.value,
            "unit": signal.unit,
            "as_of": signal.as_of.isoformat() if hasattr(signal.as_of, "isoformat") else str(signal.as_of),
            "confidence": signal.confidence,
            "source_system": signal.source_system,
            "tags": signal.tags,
            "related_departments": signal.related_departments,
            "priority_for_chairman": signal.priority_for_chairman,
            "numeric_trend": signal.numeric_trend.value if hasattr(signal.numeric_trend, "value") else str(signal.numeric_trend),
            "display_color": signal.display_color(),
            "is_trustworthy": signal.is_trustworthy(),
        }

    @staticmethod
    def _default_department_metrics(department: str) -> Dict[str, Dict[str, float]]:
        """各部門預設 metrics。"""
        defaults: Dict[str, Dict[str, Dict[str, float]]] = {
            "engineering": {
                "velocity": {"delivered": 8.0, "planned": 10.0},
                "quality": {"defect_rate": 0.05},
                "stability": {"incidents": 2.0},
                "alignment": {"goal_hit_rate": 0.9},
                "capacity": {"utilization": 0.85},
            },
            "marketing": {
                "velocity": {"delivered": 6.0, "planned": 8.0},
                "quality": {"defect_rate": 0.08},
                "stability": {"incidents": 1.0},
                "alignment": {"goal_hit_rate": 0.75},
                "capacity": {"utilization": 0.7},
            },
            "customer_service": {
                "velocity": {"delivered": 9.0, "planned": 10.0},
                "quality": {"defect_rate": 0.03},
                "stability": {"incidents": 0.5},
                "alignment": {"goal_hit_rate": 0.92},
                "capacity": {"utilization": 0.9},
            },
        }
        return defaults.get(department, defaults["engineering"])

    def get_loop_status(self, loop: Any = None) -> Dict[str, Any]:
        """Continuous Development Loop：狀態與進度。"""
        if loop is None:
            return {
                "state": "idle",
                "stop_reason": "none",
                "current_task_id": None,
                "in_progress": None,
                "last_step": None,
                "completed_count": 0,
                "founder_tickets_count": 0,
                "next_candidate": None,
            }
        return loop.status()

    def get_loop_progress(self, loop: Any = None) -> Dict[str, Any]:
        """Continuous Development Loop：Chairman 進度查詢。"""
        if loop is None:
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "project_code": None,
                "project_name": None,
                "已完成": [],
                "進行中": None,
                "下一步": None,
                "風險": [],
                "需要_Founder_介入": [],
            }
        return loop.progress()

    def get_ai_team_status(self) -> Dict[str, Any]:
        """AI Team Status：目前任務（由排程佇列與執行記錄彙整）。"""
        repo = Path(__file__).resolve().parents[3]
        scheduler = AutoScheduler()
        scheduler.reload(
            project_status_path=repo / "docs" / "sso" / "project-status.yaml",
            contracts_index_path=repo / "docs" / "sso" / "contracts-index.yaml",
        )
        queue = scheduler.propose()
        runs = self._journal.list()

        current_tasks = []
        for candidate in queue.executable[:4]:
            current_tasks.append({
                "task_id": candidate.item_id,
                "title": candidate.title or candidate.item_id,
                "source": candidate.source,
                "status": "待執行",
                "priority": candidate.priority.value if hasattr(candidate.priority, "value") else str(candidate.priority),
            })
        for candidate in queue.blocked[:4]:
            current_tasks.append({
                "task_id": candidate.item_id,
                "title": candidate.title or candidate.item_id,
                "source": candidate.source,
                "status": "被阻擋",
                "priority": candidate.priority.value if hasattr(candidate.priority, "value") else str(candidate.priority),
            })
        # 也加入最近仍在進行中的 run
        running_runs = [r for r in runs if r.status == "running"]
        for run in running_runs[:3]:
            current_tasks.append({
                "task_id": run.run_id,
                "title": run.task_name,
                "source": run.project_code or "run_journal",
                "status": "執行中",
                "priority": "normal",
            })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_tasks": len(current_tasks),
            "tasks": current_tasks,
        }

    def list_meetings(self, project_code: str = "", limit: int = 20) -> Dict[str, Any]:
        """Meetings：列出 run journal 中以 meeting- 開頭的 run。"""
        entries = self._journal.list(project_code=project_code or None, limit=limit)
        meetings = []
        for entry in entries:
            task_name = entry.task_name or ""
            if not task_name.startswith("meeting-"):
                continue
            meetings.append({
                "run_id": entry.run_id,
                "status": entry.status,
                "task_name": task_name,
                "updated_at": entry.updated_at.isoformat() if hasattr(entry.updated_at, "isoformat") else str(entry.updated_at),
                "project_code": entry.project_code,
                "project_name": entry.project_name,
            })
        return {"meetings": meetings, "count": len(meetings)}

    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Meeting：取回單一 meeting run 的近期狀態。"""
        entry = self._journal.get(meeting_id)
        if entry is None:
            return {"meeting_id": meeting_id, "status": "unknown"}
        return {
            "meeting_id": entry.run_id,
            "status": entry.status,
            "task_name": entry.task_name,
            "updated_at": entry.updated_at.isoformat() if hasattr(entry.updated_at, "isoformat") else str(entry.updated_at),
            "project_code": entry.project_code,
            "project_name": entry.project_name,
        }

    def get_cos_status(self, rt=None) -> Dict[str, Any]:
        """CoS 持續營運狀態：直接消費 CosRuntime 的 v1 envelope，不重建 raw dict。"""
        from hermes_os.cos_runtime import CosRuntime

        if rt is None:
            rt = CosRuntime()
        v1 = rt.status()
        project = v1.get("project") or {}
        project_code = project.get("code") or v1.get("project_code")
        project_name = project.get("name") or v1.get("project_name")
        cos_state = v1.get("cos_state") or v1.get("state")
        op = v1.get("operational_status", "unknown")
        idle_reason = v1.get("idle_reason")
        loop = v1.get("loop") or {}
        last_report = v1.get("last_report") or v1.get("report") or {}

        next_up = last_report.get("next_up") or {}
        next_suggestion = None
        if op == "idle":
            next_suggestion = idle_reason or "等待 Founder 下達新目標或手動触發 cycle"
        elif op == "running":
            next_suggestion = "正在執行任務，完成後自動驗收並接續下一項"
        elif op == "waiting_founder":
            next_suggestion = "等待 Founder 決策後再繼續"
        elif op == "blocked":
            next_suggestion = "系統阻塞，需 Founder 介入解除"
        elif op == "error":
            next_suggestion = "系統錯誤，需檢查 Run Journal 與 Recovery"

        founder_tickets = last_report.get("founder_tickets", []) or []
        needs_founder = bool(founder_tickets) or op == "waiting_founder"

        heartbeat = None
        heartbeat_path = Path(__file__).resolve().parents[3] / ".hermes" / "cos" / "heartbeat.json"
        try:
            if heartbeat_path.exists():
                heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except Exception:
            heartbeat = None

        return {
            "project_code": project_code,
            "project_name": project_name,
            "cos_state": cos_state,
            "operational_status": op,
            "idle_reason": idle_reason,
            "next_suggestion": next_suggestion,
            "needs_founder_intervention": needs_founder,
            "loop_state": loop.get("state"),
            "loop_stop_reason": loop.get("stop_reason"),
            "last_report": last_report,
            "heartbeat": heartbeat,
        }

    def get_cos_progress(self, rt=None) -> Dict[str, Any]:
        """CoS Chairman Progress Report：直接讀取自 CosRuntime。"""
        from hermes_os.cos_runtime import CosRuntime

        if rt is None:
            rt = CosRuntime()
        return rt.progress()

    def switch_project(self, rt=None, project_code=None, project_name=None) -> Dict[str, Any]:
        from hermes_os.cos_runtime import CosRuntime

        runtime = rt or CosRuntime()
        return runtime.switch_project(project_code=project_code, project_name=project_name)
