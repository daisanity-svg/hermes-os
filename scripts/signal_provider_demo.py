#!/usr/bin/env python3
"""Signal Provider Foundation 示範腳本。"""

from __future__ import annotations

from datetime import datetime

from hermes_os.org_learning.decision_queue import DecisionStatus, DecisionTicket, HumanDecisionQueue
from hermes_os.org_learning.providers import (
    DepartmentHealthSignalProvider,
    FinancialSnapshotProvider,
    OperationalRiskProvider,
    SignalRegistry,
    StrategicSignalDigestProvider,
)
from hermes_os.org_learning.signals import SignalCategory


def main() -> int:
    registry = SignalRegistry()
    registry.register(FinancialSnapshotProvider())
    registry.register(StrategicSignalDigestProvider())
    registry.register(
        DepartmentHealthSignalProvider(
            department="工程",
            health={
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
            },
        )
    )

    queue = HumanDecisionQueue()
    queue.enqueue(
        DecisionTicket(
            ticket_id="dt-demo-001",
            title="簽核：Q3 行銷預算重新分配",
            description="行銷部提問 Q3 預算重新分配，已附建議",
            department="行銷",
            status=DecisionStatus.PENDING,
        )
    )
    registry.register(OperationalRiskProvider(decision_queue=queue))

    print("=== Chairman Experience Phase 0 - Signal Provider Demo ===\n")

    print("--- Registry Summary ---")
    summary = registry.summary()
    for k, v in summary.items():
        print(f"{k}: {v}")
    print()

    print("--- Priority Signals for Chairman ---")
    priority = registry.fetch_priority_for_chairman()
    for signal in priority:
        color = signal.display_color()
        print(f"[{color}] {signal.title} ({signal.category.value})")
        print(f"     {signal.summary}")
        print(f"     confidence={signal.confidence:.2f} as_of={signal.as_of.isoformat()}")
        if signal.is_low_confidence_estimate:
            print("     [推估值]")
        print()

    print("--- Financial Signals (high confidence) ---")
    financial = registry.fetch_by_category(SignalCategory.FINANCIAL)
    for signal in financial:
        print(f"{signal.title}: {signal.summary} ({signal.unit})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
