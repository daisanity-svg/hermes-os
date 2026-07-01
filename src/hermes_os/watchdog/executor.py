"""Hermes OS Watchdog — ActionExecutor：以最小、安全動作處置 stagnant tasks。"""

from __future__ import annotations

from typing import List, Optional

from hermes_os.watchdog.schemas import (
    AuditRecord,
    TaskState,
    WatchdogDecision,
    WatchdogDecisionType,
)
from hermes_os.watchdog.storage import WatchdogStorage

# 安全動作白名單
ALLOWED_ACTIONS = (
    "retry_task",
    "notify_user",
    "reassign_context",
    "pause_task",
)
# 禁止關鍵字
FORBIDDEN_KEYWORDS = (
    "delete",
    "drop ",
    "reset",
    "truncate",
    "rm ",
    "force_complete",
    "unlock",
    "and",
    "&&",
    ";",
)


class ActionExecutor:
    """根據 WatchdogDecision 執行安全動作並記錄 audit。"""

    MAX_RETRY_PER_TASK = 3
    MAX_CONSECUTIVE_PROCEEDS = 3

    def __init__(self, storage: WatchdogStorage) -> None:
        self._storage = storage

    def _validate_action(self, action: str) -> bool:
        """一次只做一件事，關鍵字禁止。"""
        lower = action.lower()
        if any(k in lower for k in FORBIDDEN_KEYWORDS):
            return False
        return True

    def _allowed_decision(self, decision: WatchdogDecisionType) -> bool:
        return decision in (
            "proceed",
            "reassign_context",
            "pause",
            "notify_user",
        )

    def _execute_action(self, state: TaskState, decision: WatchdogDecision) -> str:
        """真實動作 stub（第一版僅 dry-run/紀錄，不真正改外部系統）。"""
        action = decision.action_plan[0] if decision.action_plan else "noop"
        if not self._validate_action(action):
            return f"blocked: unsafe action '{action}'"
        # TODO：實際整合 hermes-agent 的 control_center / process_adapter
        return f"dry-run:{action}"

    def execute(self, state: TaskState, decision: WatchdogDecision) -> AuditRecord:
        """套用 guards，寫入 audit。"""
        now = __import__("datetime").datetime.utcnow()
        action_taken = "skipped"
        result = "skipped"

        if not self._allowed_decision(decision.decision):
            action_taken = f"escalate:{decision.decision}"
            result = "skipped"
        else:
            action_taken = self._execute_action(state, decision)
            # 只要沒有被 block，就算 success（dry-run 定義）
            result = "success" if not action_taken.startswith("blocked:") else "failed"

        record = AuditRecord(
            ts=now,
            task_id=state.task_id,
            trigger="execute",
            state_snapshot=state,
            decision=decision,
            action_taken=action_taken,
            result=result,
            error=None if result == "success" else action_taken,
        )
        self._storage.add_audit(record)
        return record
