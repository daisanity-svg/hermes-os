"""Tests for health.py -> BusinessSignal integration."""

from __future__ import annotations

from datetime import datetime

import pytest

from hermes_os.org_learning.health import DepartmentHealthCalculator, HealthDimension
from hermes_os.org_learning.providers import DepartmentHealthSignalProvider


@pytest.fixture()
def calculator() -> DepartmentHealthCalculator:
    return DepartmentHealthCalculator()


@pytest.fixture()
def sample_health() -> dict:
    return {
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


class TestHealthSignalIntegration:
    def test_calculator_to_signal_mapping(self, calculator: DepartmentHealthCalculator, sample_health: dict) -> None:
        signals = DepartmentHealthSignalProvider(department="工程", health=sample_health).fetch_signals()
        assert len(signals) == 5
        velocity = next(s for s in signals if s.sub_category == "department_health" and "交付速度" in s.title)
        assert "8/計劃 9" in velocity.summary
        assert velocity.value == 90.0
        assert velocity.unit == "分"
        assert velocity.related_departments == ["工程"]
        assert velocity.priority_for_chairman is False  # 90 > 70

    def test_low_score_marks_priority(self, calculator: DepartmentHealthCalculator, sample_health: dict) -> None:
        sample_health["dimensions"]["stability"]["score"] = 65.0
        signals = DepartmentHealthSignalProvider(department="工程", health=sample_health).fetch_signals()
        stability = next(s for s in signals if "穩定性" in s.title)
        assert stability.priority_for_chairman is True

    def test_confidence_is_085_for_all(self, sample_health: dict) -> None:
        signals = DepartmentHealthSignalProvider(department="客服", health=sample_health).fetch_signals()
        assert all(s.confidence == 0.85 for s in signals)
        assert all(s.source_system == "command_center_department_health" for s in signals)

    def test_category_is_operational(self, sample_health: dict) -> None:
        signals = DepartmentHealthSignalProvider(department="財務", health=sample_health).fetch_signals()
        assert all(s.category.name == "OPERATIONAL" for s in signals)
        assert all(s.sub_category == "department_health" for s in signals)

    def test_overall_score_signal_when_no_dimensions(self) -> None:
        health = {
            "department": "行銷",
            "overall_score": 68.0,
            "computed_at": datetime.utcnow().isoformat(),
        }
        signals = DepartmentHealthSignalProvider(department="行銷", health=health).fetch_signals()
        assert len(signals) == 1
        assert signals[0].title == "行銷 總體健康度"
        assert signals[0].priority_for_chairman is True
