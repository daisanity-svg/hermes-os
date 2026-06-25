"""Organizational Learner — Human Decision Queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional


class DecisionStatus(StrEnum):
    """Lifecycle of a decision ticket."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


@dataclass
class DecisionTicket:
    """Minimal decision ticket for Founder/Chairman queue."""

    ticket_id: str
    title: str
    description: str = ""
    department: str = ""
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision: Optional[str] = None


class HumanDecisionQueue:
    """In-memory decision queue for Command Center nucleus."""

    def __init__(self) -> None:
        self._items: Dict[str, DecisionTicket] = {}
        self._order: List[str] = []

    def enqueue(self, ticket: DecisionTicket) -> None:
        if ticket.ticket_id in self._items:
            raise ValueError(f"Decision ticket {ticket.ticket_id} already exists")
        self._items[ticket.ticket_id] = ticket
        self._order.append(ticket.ticket_id)

    def dequeue(self, ticket_id: str) -> DecisionTicket:
        if ticket_id not in self._items:
            raise KeyError(f"Decision ticket {ticket_id} not found")
        ticket = self._items.pop(ticket_id)
        self._order.remove(ticket_id)
        return ticket

    def decide(
        self,
        ticket_id: str,
        status: DecisionStatus,
        decided_by: str,
        decision: Optional[str] = None,
    ) -> DecisionTicket:
        if ticket_id not in self._items:
            raise KeyError(f"Decision ticket {ticket_id} not found")
        ticket = self._items[ticket_id]
        ticket.status = status
        ticket.decided_at = datetime.utcnow()
        ticket.decided_by = decided_by
        ticket.decision = decision
        return ticket

    def list_pending(self) -> List[DecisionTicket]:
        return [
            self._items[tid]
            for tid in self._order
            if self._items[tid].status == DecisionStatus.PENDING
        ]

    def get(self, ticket_id: str) -> DecisionTicket:
        if ticket_id not in self._items:
            raise KeyError(f"Decision ticket {ticket_id} not found")
        return self._items[ticket_id]


def decision_ticket_to_signal(ticket: DecisionTicket) -> dict:
    """Adapter：將 DecisionTicket 轉為 Signal Provider 可讀取的 dict。"""
    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "description": ticket.description,
        "department": ticket.department,
        "status": ticket.status.value,
        "created_at": ticket.created_at.isoformat(),
    }
