"""Command Center Adapter — unify Executive Brief, Department Health, Decision Queue, Company Health via SignalRegistry."""

from __future__ import annotations

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
from hermes_os.workflow_records import WorkflowRecords


class CommandCenterAdapter:
    """統一讀取 Command Center 所需資料，避免前端直接耦合 business module。"""

    def __init__(self, registry: Optional[SignalRegistry] = None) -> None:
        self.registry = registry or SignalRegistry()
        self._register_default_providers()
        self._workflow_records = WorkflowRecords()
        self._run_statuses: Dict[str, Dict[str, Any]] = {
            "run-001": {"run_id": "run-001", "status": "running", "updated_at": "2026-06-25T14:00:00Z"},
            "run-002": {"run_id": "run-002", "status": "completed", "updated_at": "2026-06-25T12:30:00Z"},
            "run-003": {"run_id": "run-003", "status": "failed", "updated_at": "2026-06-25T10:15:00Z"},
        }
        self._inbox = HumanDecisionQueue()
        if not self._inbox.list_pending():
            self._inbox.enqueue(
                DecisionTicket(
                    ticket_id="dq-001",
                    title="Q3 行銷預算重新分配",
                    description="行銷部提案：將電視廣告預算轉為社群與差旅",
                    department="行銷",
                    status=DecisionStatus.PENDING,
                )
            )
            self._inbox.enqueue(
                DecisionTicket(
                    ticket_id="dq-002",
                    title="數學森林美術方向確認",
                    description="工程部與設計部對美術童書感程度有不同意見，需 Chairman 定調",
                    department="工程",
                    status=DecisionStatus.PENDING,
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
        return {
            "executive_brief": self.get_executive_brief(),
            "department_health": self.get_department_health(),
            "decision_queue": self.get_decision_queue_signals(),
            "company_health": self.get_company_health(),
        }

    def get_active_projects(self) -> Dict[str, Any]:
        """Active Projects：讀取 project-status.yaml 與 contracts-index.yaml。"""
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
        return {
            "project": project,
            "contracts": contracts.get("contracts", []),
        }

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
        runs = list(self._run_statuses.values())
        return {
            "count": len(runs),
            "runs": sorted(runs, key=lambda r: r.get("updated_at", ""), reverse=True),
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
