"""Tests for BusinessSignal schemas and Signal Providers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from hermes_os.org_learning.signals import (
    BusinessSignal,
    NumericTrend,
    SignalCategory,
)
from hermes_os.org_learning.providers import (
    DepartmentHealthSignalProvider,
    FinancialSnapshotProvider,
    OperationalRiskProvider,
    SignalRegistry,
    StrategicSignalDigestProvider,
)


@pytest.fixture()
def registry() -> SignalRegistry:
    return SignalRegistry()


def _demo_financial_data() -> dict:
    return {
        "runway_months": 10.0,
        "burn_monthly_k": 250.0,
        "mrr_k": 130.0,
        "nrr": 1.05,
        "cash_on_hand_k": 3000.0,
        "as_of": datetime.utcnow().isoformat(),
    }


def _demo_strategic_signals() -> list[dict]:
    return [
        {
            "title": "法規變化：AI 監管草案",
            "summary": "新的 AI 法規草案可能影響 our 產品上線時程",
            "confidence": 0.55,
            "as_of": datetime.utcnow().isoformat(),
            "priority_for_chairman": True,
            "numeric_trend": "unknown",
        },
        {
            "title": "競品 A 價格下調",
            "summary": "競品 A 降價 20%，可能衝擊 NRR",
            "confidence": 0.75,
            "as_of": datetime.utcnow().isoformat(),
            "priority_for_chairman": True,
            "numeric_trend": "down",
        },
    ]


class TestBusinessSignal:
    def test_display_color_high_confidence(self) -> None:
        signal = BusinessSignal(
            signal_id="s1",
            category=SignalCategory.FINANCIAL,
            title="Runway",
            summary="18 個月",
            confidence=0.9,
        )
        assert signal.display_color() == "green"
        assert signal.is_trustworthy() is True

    def test_display_color_low_confidence(self) -> None:
        signal = BusinessSignal(
            signal_id="s2",
            category=SignalCategory.STRATEGIC,
            title="RSS signal",
            summary="low conf",
            confidence=0.4,
        )
        assert signal.display_color() == "grey"
        assert signal.is_trustworthy() is False

    def test_display_color_medium_confidence(self) -> None:
        signal = BusinessSignal(
            signal_id="s3",
            category=SignalCategory.OPERATIONAL,
            title="Weekly report",
            summary="medium",
            confidence=0.7,
        )
        assert signal.display_color() == "yellow"
        assert signal.is_trustworthy() is False


class TestFinancialSnapshotProvider:
    def test_default_mock_returns_four_signals(self) -> None:
        provider = FinancialSnapshotProvider()
        signals = provider.fetch_signals()
        assert len(signals) == 4
        assert all(s.category == SignalCategory.FINANCIAL for s in signals)
        assert all(s.confidence == 0.9 for s in signals)

    def test_custom_data(self) -> None:
        data = _demo_financial_data()
        provider = FinancialSnapshotProvider(data=data)
        signals = provider.fetch_signals()
        titles = {s.title for s in signals}
        assert "現金流 Runway" in titles
        assert "每月 Burn rate" in titles
        assert "月經常性收入" in titles
        assert "淨收入留存率" in titles

    def test_low_runway_marks_priority(self) -> None:
        data = _demo_financial_data()
        data["runway_months"] = 8.0
        provider = FinancialSnapshotProvider(data=data)
        signals = provider.fetch_signals()
        runway_signal = next(s for s in signals if s.sub_category == "runway")
        assert runway_signal.priority_for_chairman is True


class TestStrategicSignalDigestProvider:
    def test_default_mock_returns_one_signal(self) -> None:
        provider = StrategicSignalDigestProvider()
        signals = provider.fetch_signals()
        assert len(signals) == 1
        assert signals[0].category == SignalCategory.STRATEGIC
        assert signals[0].confidence == 0.6
        assert signals[0].is_low_confidence_estimate is False  # 0.6 屬於 medium

    def test_custom_signals(self) -> None:
        provider = StrategicSignalDigestProvider(signals=_demo_strategic_signals())
        signals = provider.fetch_signals()
        assert len(signals) == 2
        titles = {s.title for s in signals}
        assert "法規變化：AI 監管草案" in titles
        assert "競品 A 價格下調" in titles
        assert signals[1].numeric_trend == NumericTrend.DOWN


class TestDepartmentHealthSignalProvider:
    def test_five_dimensions(self) -> None:
        health = {
            "department": "工程",
            "overall_score": 82.0,
            "computed_at": datetime.utcnow().isoformat(),
            "dimensions": {
                "velocity": {"score": 90.0, "narrative": "已交付 8/計劃 9"},
                "quality": {"score": 85.0, "narrative": "缺陷率 2%"},
                "stability": {"score": 75.0, "narrative": "事件數 1"},
                "alignment": {"score": 80.0, "narrative": "目標命中率 80%"},
                "capacity": {"score": 82.0, "narrative": "使用率 85%"},
            },
        }
        provider = DepartmentHealthSignalProvider(department="工程", health=health)
        signals = provider.fetch_signals()
        assert len(signals) == 5
        titles = {s.title for s in signals}
        assert "工程 交付速度" in titles
        assert "工程 品質" in titles
        assert "工程 穩定性" in titles
        assert "工程 策略對齊" in titles
        assert "工程 人力容量" in titles

    def test_empty_dimensions_falls_back_to_overall(self) -> None:
        provider = DepartmentHealthSignalProvider(
            department="行銷",
            health={"overall_score": 68.0, "computed_at": datetime.utcnow().isoformat()},
        )
        signals = provider.fetch_signals()
        assert len(signals) == 1
        assert signals[0].title == "行銷 總體健康度"
        assert signals[0].priority_for_chairman is True

    def test_confidence_is_hardcoded_high(self) -> None:
        provider = DepartmentHealthSignalProvider(
            department="客服",
            health={
                "overall_score": 90.0,
                "computed_at": datetime.utcnow().isoformat(),
                "dimensions": {
                    "velocity": {"score": 95.0, "narrative": "快"},
                },
            },
        )
        signals = provider.fetch_signals()
        assert all(s.confidence == 0.85 for s in signals)


class TestOperationalRiskProvider:
    def test_empty_queue_returns_empty(self) -> None:
        provider = OperationalRiskProvider()
        assert provider.fetch_signals() == []

    def test_pending_ticket_becomes_signal(self) -> None:
        tickets = [
            {
                "ticket_id": "t1",
                "title": "Q3 預算簽核",
                "description": "行銷部提問 Q3 預算重新分配",
                "department": "行銷",
                "status": "PENDING",
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
        provider = OperationalRiskProvider(pending_decision_tickets=tickets)
        signals = provider.fetch_signals()
        assert len(signals) == 1
        assert signals[0].category == SignalCategory.RISK
        assert signals[0].priority_for_chairman is True
        assert signals[0].confidence == 0.75
        assert signals[0].sub_category == "human_decision_pending"


class TestSignalRegistry:
    def test_register_and_fetch_all(self, registry: SignalRegistry) -> None:
        registry.register(FinancialSnapshotProvider())
        registry.register(StrategicSignalDigestProvider())
        all_signals = registry.fetch_all()
        assert len(all_signals) == 5  # 4 financial + 1 strategic

    def test_fetch_by_category(self, registry: SignalRegistry) -> None:
        registry.register(FinancialSnapshotProvider())
        financial = registry.fetch_by_category(SignalCategory.FINANCIAL)
        assert len(financial) == 4
        assert all(s.category == SignalCategory.FINANCIAL for s in financial)

    def test_fetch_priority_for_chairman(self, registry: SignalRegistry) -> None:
        data = _demo_financial_data()
        data["runway_months"] = 8.0
        registry.register(FinancialSnapshotProvider(data=data))
        registry.register(StrategicSignalDigestProvider(signals=_demo_strategic_signals()))
        priority = registry.fetch_priority_for_chairman()
        assert any(s.sub_category == "runway" for s in priority)
        assert any(s.title == "法規變化：AI 監管草案" for s in priority)

    def test_summary_counts(self, registry: SignalRegistry) -> None:
        registry.register(FinancialSnapshotProvider())
        registry.register(StrategicSignalDigestProvider())
        summary = registry.summary()
        assert summary["total"] == 5
        assert summary["high_confidence"] == 4  # 4 financial signals at 0.9
        assert summary["low_confidence"] == 0  # default strategic is 0.6 (medium)
        assert summary["by_category"]["Financial"] == 4
        assert summary["by_category"]["Strategic"] == 1

    def test_fetch_by_confidence(self, registry: SignalRegistry) -> None:
        registry.register(FinancialSnapshotProvider())
        registry.register(StrategicSignalDigestProvider())
        high = registry.fetch_by_confidence(min_confidence=0.8)
        assert len(high) == 4
        assert all(s.confidence >= 0.8 for s in high)
