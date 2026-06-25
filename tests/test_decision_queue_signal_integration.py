"""Tests for decision_queue.py -> Risk signal integration."""

from __future__ import annotations

from datetime import datetime

import pytest

from hermes_os.org_learning.decision_queue import DecisionStatus, DecisionTicket, HumanDecisionQueue
from hermes_os.org_learning.providers import OperationalRiskProvider


@pytest.fixture()
def queue() -> HumanDecisionQueue:
    return HumanDecisionQueue()


class TestDecisionQueueSignalIntegration:
    def test_empty_queue_produces_no_signals(self, queue: HumanDecisionQueue) -> None:
        provider = OperationalRiskProvider(decision_queue=queue)
        assert provider.fetch_signals() == []

    def test_pending_ticket_becomes_risk_signal(self, queue: HumanDecisionQueue) -> None:
        ticket = DecisionTicket(
            ticket_id="dt-001",
            title="簽核：Q3 行銷預算重新分配",
            description="行銷部提問 Q3 預算重新分配，建議核准差旅+社群",
            department="行銷",
            status=DecisionStatus.PENDING,
        )
        queue.enqueue(ticket)
        provider = OperationalRiskProvider(decision_queue=queue)
        signals = provider.fetch_signals()
        assert len(signals) == 1
        signal = signals[0]
        assert signal.category.name == "RISK"
        assert signal.sub_category == "human_decision_pending"
        assert signal.title == "簽核：Q3 行銷預算重新分配"
        assert signal.priority_for_chairman is True
        assert signal.confidence == 0.75
        assert signal.source_system == "decision_queue_watchdog"
        assert signal.related_departments == ["行銷"]

    def test_non_pending_tickets_are_skipped(self, queue: HumanDecisionQueue) -> None:
        approved = DecisionTicket(
            ticket_id="dt-002",
            title="已簽核事項",
            description="done",
            department="工程",
            status=DecisionStatus.APPROVED,
        )
        queue.enqueue(approved)
        provider = OperationalRiskProvider(decision_queue=queue)
        assert provider.fetch_signals() == []

    def test_mixed_queue_only_pending_signals(self, queue: HumanDecisionQueue) -> None:
        pending = DecisionTicket(
            ticket_id="dt-003",
            title="等待",
            description="pending",
            department="客服",
            status=DecisionStatus.PENDING,
        )
        approved = DecisionTicket(
            ticket_id="dt-004",
            title="已處理",
            description="done",
            department="客服",
            status=DecisionStatus.APPROVED,
        )
        queue.enqueue(pending)
        queue.enqueue(approved)
        provider = OperationalRiskProvider(decision_queue=queue)
        signals = provider.fetch_signals()
        assert len(signals) == 1
        assert signals[0].title == "等待"

    def test_fallback_to_pending_ticket_list(self) -> None:
        tickets = [
            {
                "ticket_id": "dt-005",
                "title": "手動輸入票",
                "description": "fallback",
                "department": "產品",
                "status": "PENDING",
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
        provider = OperationalRiskProvider(pending_decision_tickets=tickets)
        signals = provider.fetch_signals()
        assert len(signals) == 1
        assert signals[0].related_departments == ["產品"]

    def test_as_of_preserves_creation_time(self, queue: HumanDecisionQueue) -> None:
        now = datetime.utcnow()
        ticket = DecisionTicket(
            ticket_id="dt-006",
            title="逾期決策",
            description="old",
            department="行銷",
            status=DecisionStatus.PENDING,
            created_at=now,
        )
        queue.enqueue(ticket)
        provider = OperationalRiskProvider(decision_queue=queue)
        signals = provider.fetch_signals()
        assert len(signals) == 1
        # as_of 應該接近 created_at
        delta = abs((signals[0].as_of - now).total_seconds())
        assert delta < 1
