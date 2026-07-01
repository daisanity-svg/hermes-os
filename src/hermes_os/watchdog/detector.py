"""Hermes OS Watchdog — StagnationDetector：任務停滯偵測邏輯。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from hermes_os.watchdog.schemas import TaskState, TaskStatus

# 停滯條件矩陣（分鐘為單位）
STAGNATION_RULES: Dict[str, int] = {
    "idle_threshold_minutes": 15,  # 規則 A：無活動超過 15 分鐘
    "user_reply_idle_minutes": 25,  # 規則 B：使用者無回覆超過 25 分鐘
    "same_status_minutes": 30,  # 規則 C：同一狀態停留超過 30 分鐘
    "max_consecutive_idle_checks": 3,  # 規則 D：連續 3 輪無進展
    "error_retry_limit": 2,  # 規則 E：同一錯誤重複 2 次
}


def _elapsed_minutes(ts: datetime, now: datetime) -> float:
    return (now - ts).total_seconds() / 60.0


def _is_stagnant(state: TaskState, now: datetime) -> bool:
    """依 STAGNATION_RULES 判斷單一 TaskState 是否停滯。"""
    if state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PAUSED, TaskStatus.ESCALATED):
        return False

    # 規則 A
    if _elapsed_minutes(state.last_activity_ts, now) > STAGNATION_RULES[
        "idle_threshold_minutes"
    ]:
        return True

    # 規則 B
    if state.last_user_reply_ts and _elapsed_minutes(
        state.last_user_reply_ts, now
    ) > STAGNATION_RULES["user_reply_idle_minutes"]:
        return True

    # 規則 C — 同一狀態停留過久
    if _elapsed_minutes(
        state.last_activity_ts, now
    ) > STAGNATION_RULES["same_status_minutes"]:
        return True

    # 規則 D
    if state.consecutive_idle_checks >= STAGNATION_RULES["max_consecutive_idle_checks"]:
        return True

    # 規則 E
    if state.error_summary and state.consecutive_idle_checks >= STAGNATION_RULES[
        "error_retry_limit"
    ]:
        return True

    return False


def stagnation_score(state: TaskState, now: datetime) -> int:
    """停滯優先級分數；>=2 觸發 GPT Supervisor。"""
    score = 0
    if _is_stagnant(state, now):
        score += 1
    if state.consecutive_idle_checks >= STAGNATION_RULES["max_consecutive_idle_checks"]:
        score += 1
    return score


class StagnationDetector:
    """批次掃描 task list，輸出 stagnant tasks 並更新 consecutive checks。"""

    def scan(self, states: list[TaskState], now: datetime | None = None) -> list[TaskState]:
        if now is None:
            now = datetime.utcnow()
        stagnant: list[TaskState] = []
        for state in states:
            if _is_stagnant(state, now):
                if state.consecutive_idle_checks < 255:  # u8 soft cap
                    # 注意：這邊只做 in-memory 計算，實際持久化由 caller 負責
                    object.__setattr__(
                        state,
                        "consecutive_idle_checks",
                        state.consecutive_idle_checks + 1,
                    )
                    # 維持 frozen 違規可行性：TaskState 是 BaseModel，使用 object.__setattr__
                stagnant.append(state)
        return stagnant
