"""Organizational Learner — Business Signal Providers."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from hermes_os.org_learning.signals import (
    BusinessSignal,
    NumericTrend,
    SignalCategory,
)
from hermes_os.org_learning.decision_queue import (
    DecisionStatus,
    HumanDecisionQueue,
)


class AbstractSignalProvider(ABC):
    """抽象 Business Signal Provider 基底類別。"""

    provider_id: str
    category: SignalCategory
    source_system: str

    def __init__(self, provider_id: Optional[str] = None) -> None:
        self.provider_id = provider_id or self.__class__.__name__

    @abstractmethod
    def fetch_signals(self) -> List[BusinessSignal]:
        """抓取目前可用的 business signals，回傳標準化清單。"""

    def health_status(self) -> Dict[str, object]:
        """回傳 provider 的健康狀態（可選）。"""
        return {
            "provider_id": self.provider_id,
            "status": "ok",
            "last_checked": datetime.utcnow().isoformat(),
        }


class FinancialSnapshotProvider(AbstractSignalProvider):
    """Company Financial Snapshot 的 Signal Provider。"""

    source_system = "cfo_mock_data"
    category = SignalCategory.FINANCIAL

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(provider_id="financial_snapshot_provider")
        self._data = data or self._default_mock_data()

    @staticmethod
    def _default_mock_data() -> Dict[str, Any]:
        return {
            "runway_months": 18.0,
            "burn_monthly_k": 240.0,
            "mrr_k": 120.0,
            "nrr": 1.18,
            "cash_on_hand_k": 4320.0,
            "as_of": datetime.utcnow().isoformat(),
        }

    def _extract(self) -> Dict[str, Any]:
        return self._data

    def fetch_signals(self) -> List[BusinessSignal]:
        data = self._extract()
        as_of_raw = data.get("as_of", datetime.utcnow().isoformat())
        if isinstance(as_of_raw, str):
            as_of = datetime.fromisoformat(as_of_raw)
        else:
            as_of = as_of_raw

        runway = float(data.get("runway_months", 0.0))
        burn = float(data.get("burn_monthly_k", 0.0))
        mrr = float(data.get("mrr_k", 0.0))
        nrr = float(data.get("nrr", 0.0))

        return [
            BusinessSignal(
                signal_id=str(uuid.uuid4()),
                category=self.category,
                sub_category="runway",
                title="現金流 Runway",
                summary=f"Runway 約 {runway:.1f} 個月",
                value=runway,
                unit="個月",
                as_of=as_of,
                confidence=0.9,
                source_system=self.source_system,
                priority_for_chairman=runway < 12,
                numeric_trend=NumericTrend.UNKNOWN,
                is_low_confidence_estimate=False,
            ),
            BusinessSignal(
                signal_id=str(uuid.uuid4()),
                category=self.category,
                sub_category="burn",
                title="每月 Burn rate",
                summary=f"月燒 {burn:.0f}K",
                value=burn,
                unit="$K/月",
                as_of=as_of,
                confidence=0.9,
                source_system=self.source_system,
                priority_for_chairman=False,
                numeric_trend=NumericTrend.FLAT,
                is_low_confidence_estimate=False,
            ),
            BusinessSignal(
                signal_id=str(uuid.uuid4()),
                category=self.category,
                sub_category="mrr",
                title="月經常性收入",
                summary=f"MRR ${mrr:.0f}K",
                value=mrr,
                unit="$K",
                as_of=as_of,
                confidence=0.9,
                source_system=self.source_system,
                priority_for_chairman=True,
                numeric_trend=NumericTrend.UP,
                is_low_confidence_estimate=False,
            ),
            BusinessSignal(
                signal_id=str(uuid.uuid4()),
                category=self.category,
                sub_category="nrr",
                title="淨收入留存率",
                summary=f"NRR {nrr:.0%}",
                value=nrr,
                unit="%",
                as_of=as_of,
                confidence=0.9,
                source_system=self.source_system,
                priority_for_chairman=nrr < 1.0,
                numeric_trend=NumericTrend.UP,
                is_low_confidence_estimate=False,
            ),
        ]


class StrategicSignalDigestProvider(AbstractSignalProvider):
    """Strategic Signal Digest 的 Signal Provider。"""

    source_system = "rss_mock_digest"
    category = SignalCategory.STRATEGIC

    def __init__(self, signals: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(provider_id="strategic_signal_digest_provider")
        self._signals = signals or self._default_mock_signals()

    @staticmethod
    def _default_mock_signals() -> List[Dict[str, Any]]:
        return [
            {
                "title": "競品 A 發佈會",
                "summary": "競品 A 發布 AI 助手，可能衝擊 our positioning",
                "confidence": 0.6,
                "as_of": datetime.utcnow().isoformat(),
                "priority_for_chairman": True,
                "numeric_trend": "unknown",
            }
        ]

    def fetch_signals(self) -> List[BusinessSignal]:
        results: List[BusinessSignal] = []
        for item in self._signals:
            as_of_raw = item.get("as_of", datetime.utcnow().isoformat())
            if isinstance(as_of_raw, str):
                as_of = datetime.fromisoformat(as_of_raw)
            else:
                as_of = as_of_raw
            trend = item.get("numeric_trend", "unknown")
            if isinstance(trend, str):
                try:
                    numeric_trend = NumericTrend(trend)
                except ValueError:
                    numeric_trend = NumericTrend.UNKNOWN
            else:
                numeric_trend = NumericTrend.UNKNOWN
            results.append(
                BusinessSignal(
                    signal_id=str(uuid.uuid4()),
                    category=self.category,
                    sub_category="market_news",
                    title=str(item.get("title", "")),
                    summary=str(item.get("summary", "")),
                    confidence=float(item.get("confidence", 0.5)),
                    as_of=as_of,
                    source_system=self.source_system,
                    priority_for_chairman=bool(item.get("priority_for_chairman", False)),
                    numeric_trend=numeric_trend,
                    is_low_confidence_estimate=float(item.get("confidence", 0.5)) < 0.5,
                )
            )
        return results


class DepartmentHealthSignalProvider(AbstractSignalProvider):
    """Department Health -> Business Signal 的 Adapter Provider。"""

    source_system = "command_center_department_health"
    category = SignalCategory.OPERATIONAL

    def __init__(
        self,
        department: str,
        health: Optional[Dict[str, Any]] = None,
        real_data_loader: Optional[Any] = None,
    ) -> None:
        super().__init__(provider_id=f"dept_health_{department}")
        self._department = department
        self._health = health or {}
        self._real_data_loader = real_data_loader

    def _build_signals_from_health(self, health: Dict[str, Any]) -> List[BusinessSignal]:
        results: List[BusinessSignal] = []
        dimensions = health.get("dimensions", {})
        overall = float(health.get("overall_score", 0.0))
        as_of_raw = health.get("computed_at", datetime.utcnow().isoformat())
        if isinstance(as_of_raw, str):
            as_of = datetime.fromisoformat(as_of_raw)
        elif isinstance(as_of_raw, datetime):
            as_of = as_of_raw
        else:
            as_of = datetime.utcnow()

        dimension_titles = {
            "velocity": f"{self._department} 交付速度",
            "quality": f"{self._department} 品質",
            "stability": f"{self._department} 穩定性",
            "alignment": f"{self._department} 策略對齊",
            "capacity": f"{self._department} 人力容量",
        }

        for dim_key, dim_data in dimensions.items():
            dim_data = dict(dim_data)
            score = float(dim_data.get("score", 0.0))
            narrative = str(dim_data.get("narrative", ""))
            title = dimension_titles.get(dim_key, f"{self._department} {dim_key}")
            summary = f"{title} {score:.0f} 分。{narrative}"
            results.append(
                BusinessSignal(
                    signal_id=str(uuid.uuid4()),
                    category=self.category,
                    sub_category="department_health",
                    title=title,
                    summary=summary,
                    value=score,
                    unit="分",
                    as_of=as_of,
                    confidence=0.85,
                    source_system=self.source_system,
                    related_departments=[self._department],
                    priority_for_chairman=score < 70,
                    numeric_trend=NumericTrend.UNKNOWN,
                    is_low_confidence_estimate=False,
                )
            )

        if not results:
            results.append(
                BusinessSignal(
                    signal_id=str(uuid.uuid4()),
                    category=self.category,
                    sub_category="department_health_overall",
                    title=f"{self._department} 總體健康度",
                    summary=f"總分 {overall:.0f} 分",
                    value=overall,
                    unit="分",
                    as_of=as_of,
                    confidence=0.85,
                    source_system=self.source_system,
                    related_departments=[self._department],
                    priority_for_chairman=overall < 70,
                    numeric_trend=NumericTrend.UNKNOWN,
                    is_low_confidence_estimate=False,
                )
            )
        return results

    def fetch_signals(self) -> List[BusinessSignal]:
        if self._real_data_loader is not None:
            try:
                real_health = self._real_data_loader(self._department)
                if isinstance(real_health, dict):
                    return self._build_signals_from_health(real_health)
            except Exception:
                pass
        return self._build_signals_from_health(self._health)


class OperationalRiskProvider(AbstractSignalProvider):
    """Decision Queue + Watchdog -> Operational Risk Signals。"""

    source_system = "decision_queue_watchdog"
    category = SignalCategory.RISK

    def __init__(
        self,
        decision_queue: Optional[HumanDecisionQueue] = None,
        pending_decision_tickets: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(provider_id="operational_risk_provider")
        self._decision_queue = decision_queue
        self._pending_tickets = pending_decision_tickets or []

    def _tickets_from_queue(self) -> List[Dict[str, Any]]:
        if self._decision_queue is None:
            return self._pending_tickets
        return [
            {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "description": ticket.description,
                "department": ticket.department,
                "status": ticket.status.value,
                "created_at": ticket.created_at.isoformat(),
            }
            for ticket in self._decision_queue.list_pending()
        ]

    def fetch_signals(self) -> List[BusinessSignal]:
        results: List[BusinessSignal] = []
        for ticket in self._tickets_from_queue():
            as_of = datetime.utcnow()
            created = ticket.get("created_at")
            if isinstance(created, str):
                try:
                    as_of = datetime.fromisoformat(created)
                except ValueError:
                    pass
            dept = ticket.get("department")
            results.append(
                BusinessSignal(
                    signal_id=str(uuid.uuid4()),
                    category=self.category,
                    sub_category="human_decision_pending",
                    title=str(ticket.get("title", "")),
                    summary=str(ticket.get("description", "")),
                    value=None,
                    unit=None,
                    as_of=as_of,
                    confidence=0.75,
                    source_system=self.source_system,
                    related_departments=[str(dept)] if dept else [],
                    priority_for_chairman=True,
                    numeric_trend=NumericTrend.UNKNOWN,
                    is_low_confidence_estimate=False,
                )
            )
        return results


class SignalRegistry:
    """Provider Registry：註冊、抓取、過滤 signals。"""

    def __init__(self) -> None:
        self._providers: Dict[str, AbstractSignalProvider] = {}

    def register(self, provider: AbstractSignalProvider) -> None:
        self._providers[provider.provider_id] = provider

    def unregister(self, provider_id: str) -> None:
        self._providers.pop(provider_id, None)

    def fetch_all(self) -> List[BusinessSignal]:
        signals: List[BusinessSignal] = []
        errors: List[str] = []
        for provider in self._providers.values():
            try:
                signals.extend(provider.fetch_signals())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.provider_id}: {exc}")
        return signals

    def fetch_by_category(self, category: SignalCategory) -> List[BusinessSignal]:
        return [s for s in self.fetch_all() if s.category == category]

    def fetch_priority_for_chairman(self) -> List[BusinessSignal]:
        return [s for s in self.fetch_all() if s.priority_for_chairman]

    def fetch_by_confidence(self, min_confidence: float = 0.0) -> List[BusinessSignal]:
        return [s for s in self.fetch_all() if s.confidence >= min_confidence]

    def summary(self) -> Dict[str, Any]:
        all_signals = self.fetch_all()
        return {
            "total": len(all_signals),
            "priority_for_chairman": sum(1 for s in all_signals if s.priority_for_chairman),
            "high_confidence": sum(1 for s in all_signals if s.confidence >= 0.85),
            "low_confidence": sum(1 for s in all_signals if s.confidence < 0.5),
            "by_category": {
                cat.value: sum(1 for s in all_signals if s.category == cat)
                for cat in SignalCategory
            },
        }
