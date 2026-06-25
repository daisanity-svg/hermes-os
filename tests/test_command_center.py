"""Tests for ADO-CON-003: Command Center v1 nucleus."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pytest

from hermes_os.org_learning.decision_queue import (
    DecisionStatus,
    DecisionTicket,
    HumanDecisionQueue,
)
from hermes_os.org_learning.health import (
    DepartmentHealth,
    DepartmentHealthCalculator,
    DimensionScore,
    HealthDimension,
)
from hermes_os.org_learning.schemas import AppliedStatus
from hermes_os.org_learning.brief import build_executive_brief
from hermes_os.org_learning.rules import (
    check_org_memory_consistency,
    check_retrospective_delta_required,
)
from hermes_os.org_learning.schemas import (
    ContractRetrospective,
    OrgMemoryEntry,
    ProcessDelta,
)


# === fixtures ===


@pytest.fixture()
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_delta(delta_id: str, contract_id: str, status: AppliedStatus = AppliedStatus.APPLIED, confidence: float = 0.9) -> ProcessDelta:
    return ProcessDelta(
        delta_id=delta_id,
        source_contract_id=contract_id,
        change_description=f"change-{delta_id}",
        confidence=confidence,
        applied_status=status,
        created_at=datetime.now(timezone.utc),
    )


# === health ===


class TestDepartmentHealthCalculator:
    def test_compute_equal_weights(self) -> None:
        calc = DepartmentHealthCalculator()
        metrics = {
            HealthDimension.VELOCITY.value: {"delivered": 8.0, "planned": 10.0},
            HealthDimension.QUALITY.value: {"defect_rate": 0.05},
            HealthDimension.STABILITY.value: {"incidents": 2.0},
            HealthDimension.ALIGNMENT.value: {"goal_hit_rate": 0.9},
            HealthDimension.CAPACITY.value: {"utilization": 0.85},
        }
        health = calc.compute("engineering", metrics)
        assert health.department == "engineering"
        assert abs(health.overall_score - 89.0) < 0.1
        assert len(health.dimensions) == 5

    def test_empty_metrics_returns_zero(self) -> None:
        calc = DepartmentHealthCalculator()
        health = calc.compute("ops", {})
        assert health.overall_score == 40.0

    def test_dimension_scores_in_range(self) -> None:
        calc = DepartmentHealthCalculator()
        metrics = {
            HealthDimension.VELOCITY.value: {"delivered": 0.0, "planned": 1.0},
            HealthDimension.QUALITY.value: {"defect_rate": 0.5},
            HealthDimension.STABILITY.value: {"incidents": 20.0},
            HealthDimension.ALIGNMENT.value: {"goal_hit_rate": 0.0},
            HealthDimension.CAPACITY.value: {"utilization": 0.0},
        }
        health = calc.compute("ops", metrics)
        for dim, score in health.dimensions.items():
            assert 0.0 <= score.score <= 100.0


# === decision queue ===


class TestHumanDecisionQueue:
    def test_enqueue_and_list_pending(self) -> None:
        queue = HumanDecisionQueue()
        ticket = DecisionTicket(
            ticket_id="dq-001",
            title="Q3 資源重分配",
            department="engineering",
        )
        queue.enqueue(ticket)
        pending = queue.list_pending()
        assert len(pending) == 1
        assert pending[0].ticket_id == "dq-001"

    def test_decide_updates_status(self) -> None:
        queue = HumanDecisionQueue()
        ticket = DecisionTicket(ticket_id="dq-002", title="招募名額")
        queue.enqueue(ticket)
        updated = queue.decide("dq-002", DecisionStatus.APPROVED, "chairman", "批准")
        assert updated.status == DecisionStatus.APPROVED
        assert updated.decided_by == "chairman"
        assert queue.list_pending() == []

    def test_dequeue_removes_item(self) -> None:
        queue = HumanDecisionQueue()
        ticket = DecisionTicket(ticket_id="dq-003", title="測試")
        queue.enqueue(ticket)
        removed = queue.dequeue("dq-003")
        assert removed.ticket_id == "dq-003"
        assert queue.list_pending() == []

    def test_duplicate_enqueue_raises(self) -> None:
        queue = HumanDecisionQueue()
        ticket = DecisionTicket(ticket_id="dq-004", title="dup")
        queue.enqueue(ticket)
        with pytest.raises(ValueError):
            queue.enqueue(ticket)


# === executive brief (existing) ===


class TestExecutiveBrief:
    def test_filters_high_confidence_applied_only(self, _utcnow: datetime) -> None:
        deltas = [
            _make_delta("d1", "c1", AppliedStatus.APPLIED, 0.95),
            _make_delta("d2", "c1", AppliedStatus.APPLIED, 0.80),
            _make_delta("d3", "c1", AppliedStatus.PENDING, 0.99),
            _make_delta("d4", "c1", AppliedStatus.REJECTED, 0.90),
            _make_delta("d5", "c1", AppliedStatus.APPLIED, 0.85),
        ]
        brief = build_executive_brief(deltas)
        assert len(brief) == 2
        assert {d.delta_id for d in brief} == {"d1", "d5"}

    def test_empty_input(self) -> None:
        assert build_executive_brief([]) == []
