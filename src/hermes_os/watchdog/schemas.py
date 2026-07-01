"""Hermes OS Watchdog — 共享型別與 Pydantic schema。"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    """Watchdog 所監控的任務狀態。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ESCALATED = "escalated"


WatchdogDecisionType = str  # 相容 pyright，實務以 WatchdogDecisionType 列舉檢驗
AuditResultType = str  # 相容 pyright，實務以 AuditResultType 列舉檢驗


class TaskState(BaseModel):
    """被監控的最小狀態單位。"""

    model_config = {"extra": "ignore"}

    task_id: str = Field(..., description="唯一任務識別碼")
    project: str = Field(..., description="所屬專案名稱")
    status: TaskStatus = Field(..., description="目前狀態")
    last_activity_ts: datetime = Field(..., description="最後活動時間戳記")
    last_user_reply_ts: Optional[datetime] = Field(
        default=None, description="最後使用者回覆時間"
    )
    consecutive_idle_checks: int = Field(
        default=0, description="連續閒置檢查次數"
    )
    error_summary: Optional[str] = Field(
        default=None, description="錯誤摘要"
    )
    blockers: List[str] = Field(
        default_factory=list, description="阻塞事項清單"
    )
    current_action: Optional[str] = Field(
        default=None, description="目前執行中的動作"
    )
    owner: Optional[str] = Field(
        default=None, description="負責人"
    )


class WatchdogDecision(BaseModel):
    """GPT Supervisor 針對單一任務做出的決策。"""

    model_config = {"extra": "ignore"}

    task_id: str = Field(..., description="對應的任務 ID")
    decision: WatchdogDecisionType = Field(
        ..., description="決策類型"
    )
    reason: str = Field(..., description="一行中文結論")
    action_plan: List[str] = Field(
        ..., max_length=3, description="可執行的步驟（最多 3 項）"
    )
    risk: str = Field(..., description="潛在風險描述")
    next_check: Optional[datetime] = Field(
        default=None, description="下次檢查時間（ISO8601 或 null）"
    )
    requires_human: bool = Field(
        default=False, description="是否需要人工介入"
    )


class AuditRecord(BaseModel):
    """單次 watchdog 檢查的完整 audit log。"""

    model_config = {"extra": "ignore"}

    ts: datetime = Field(..., description="檢查時間戳記")
    task_id: str = Field(..., description="任務 ID")
    trigger: str = Field(..., description="觸發原因（detected/gpt_decision/execute）")
    state_snapshot: TaskState = Field(..., description="檢查當下的任務狀態")
    decision: Optional[WatchdogDecision] = Field(
        default=None, description="若觸發 gpt 則記錄決策"
    )
    action_taken: Optional[str] = Field(
        default=None, description="實際執行的動作"
    )
    result: AuditResultType = Field(
        ..., description="執行結果"
    )
    error: Optional[str] = Field(
        default=None, description="錯誤訊息（若有）"
    )
