"""Organizational Learner — Executive Brief minimal filter."""

from __future__ import annotations

from typing import List

from hermes_os.org_learning.schemas import AppliedStatus, ProcessDelta
from hermes_os.org_learning.signals import BusinessSignal, SignalCategory


def build_executive_brief(
    process_deltas: List[ProcessDelta],
) -> List[ProcessDelta]:
    """產生 Executive Brief：僅揭露信心值 >= 0.85 且已套用的程序差異。

    參數：
        process_deltas: 原始程序差異清單。

    回傳：
        符合 confidence >= 0.85 且 applied_status == applied 的 ProcessDelta 清單。
    """
    return [
        d
        for d in process_deltas
        if d.confidence >= 0.85 and d.applied_status == AppliedStatus.APPLIED
    ]


def signals_to_executive_brief_items(
    signals: List[BusinessSignal],
) -> List[BusinessSignal]:
    """將 signals 過濾成 Executive Brief 可用的項目。

    規則：
        - confidence >= 0.85
        - 或 priority_for_chairman == True
    """
    return [
        s
        for s in signals
        if s.confidence >= 0.85 or s.priority_for_chairman
    ]

