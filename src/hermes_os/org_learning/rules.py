"""Organizational Learner — Watchdog boundary rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from hermes_os.org_learning.schemas import (
    ContractRetrospective,
    OrgMemoryEntry,
    ProcessDelta,
)


@dataclass
class OrgLearningRuleResult:
    """單一規則的驗證結果。"""

    rule_name: str
    passed: bool
    detail: str = ""


def check_org_memory_consistency(
    entries: List[OrgMemoryEntry],
) -> OrgLearningRuleResult:
    """檢查 OrgMemory 資料一致性邊界。

    規則 org_memory.consistency：
    - confidence 必須在 [0, 1]
    - access_count 不可小於 0
    - category 不可為空
    """
    invalid_confidence = [e.memory_id for e in entries if not (0.0 <= e.confidence <= 1.0)]
    invalid_access = [e.memory_id for e in entries if e.access_count < 0]
    empty_category = [e.memory_id for e in entries if not e.category.strip()]

    if invalid_confidence or invalid_access or empty_category:
        parts = []
        if invalid_confidence:
            parts.append(f"confidence 越界：{invalid_confidence}")
        if invalid_access:
            parts.append(f"access_count 負值：{invalid_access}")
        if empty_category:
            parts.append(f"category 為空：{empty_category}")
        return OrgLearningRuleResult(
            rule_name="org_memory.consistency",
            passed=False,
            detail="；".join(parts),
        )
    return OrgLearningRuleResult(
        rule_name="org_memory.consistency",
        passed=True,
        detail="所有 org_memory 項目通過一致性檢查",
    )


def check_retrospective_delta_required(
    retrospective: Optional[ContractRetrospective],
    source_deltas: List[ProcessDelta],
) -> OrgLearningRuleResult:
    """檢查 retrospective.delta_required 邊界。

    規則 retrospective.delta_required：
    - 若 retrospective 存在，必須至少有一個來源為同一 contract_id 的 ProcessDelta
    - 且至少有一個 delta 的 applied_status == applied
    """
    if retrospective is None:
        return OrgLearningRuleResult(
            rule_name="retrospective.delta_required",
            passed=True,
            detail="無 retrospective，規則不適用",
        )

    related = [d for d in source_deltas if d.source_contract_id == retrospective.contract_id]
    has_applied = any(d.applied_status.value == "applied" for d in related)

    if not related:
        return OrgLearningRuleResult(
            rule_name="retrospective.delta_required",
            passed=False,
            detail=f"retrospective {retrospective.retrospective_id} 對應的契約 {retrospective.contract_id} 缺少 ProcessDelta",
        )
    if not has_applied:
        return OrgLearningRuleResult(
            rule_name="retrospective.delta_required",
            passed=False,
            detail=f"retrospective {retrospective.retrospective_id} 對應的 ProcessDelta 皆未套用",
        )
    return OrgLearningRuleResult(
        rule_name="retrospective.delta_required",
        passed=True,
        detail=f"retrospective {retrospective.retrospective_id} 已對應 {len(related)} 筆 ProcessDelta 且包含 applied 狀態",
    )
