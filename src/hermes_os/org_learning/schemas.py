"""Organizational Learner — minimal Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AppliedStatus(StrEnum):
    """Process delta 的應用狀態。"""

    APPLIED = "applied"
    PENDING = "pending"
    REJECTED = "rejected"
    OBSOLETE = "obsolete"


class ContractRetrospective(BaseModel):
    """單一契約執行完成後的回顾邊界資料。"""

    model_config = {"extra": "ignore"}

    retrospective_id: str = Field(..., description="回顧唯一識別碼")
    contract_id: str = Field(..., description="對應的契約 ID")
    summary: str = Field(..., description="執行結論摘要")
    lessons_learned: List[str] = Field(
        default_factory=list,
        description="學到的重要事項",
    )
    created_at: datetime = Field(..., description="建立時間（UTC）")
    tags: List[str] = Field(
        default_factory=list,
        description="分類標籤",
    )


class OrgMemoryEntry(BaseModel):
    """組織共同記憶的最小邊界資料。"""

    model_config = {"extra": "ignore"}

    memory_id: str = Field(..., description="記憶唯一識別碼")
    category: str = Field(..., description="記憶分類")
    content: str = Field(..., description="記憶內容")
    source_contract_ids: List[str] = Field(
        default_factory=list,
        description="來源契約 ID 清單",
    )
    confidence: float = Field(
        default=1.0,
        description="可信度 0~1",
    )
    created_at: datetime = Field(..., description="建立時間（UTC）")
    last_accessed_at: Optional[datetime] = Field(
        default=None,
        description="最後被取用時間",
    )
    access_count: int = Field(
        default=0,
        description="取用次數",
    )


class ProcessRule(BaseModel):
    """治理程序規則的最小邊界資料。"""

    model_config = {"extra": "ignore"}

    rule_id: str = Field(..., description="規則唯一識別碼")
    name: str = Field(..., description="規則名稱")
    description: str = Field(..., description="規則描述")
    trigger_condition: str = Field(..., description="觸發條件（中文敘述）")
    action: str = Field(..., description="對應處理動作")
    confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="啟動所需最低信心值",
    )
    active: bool = Field(default=True, description="是否啟用")
    created_at: datetime = Field(..., description="建立時間（UTC）")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="最近一次更新時間",
    )


class ProcessDelta(BaseModel):
    """程序差異的最小邊界資料。"""

    model_config = {"extra": "ignore"}

    delta_id: str = Field(..., description="差異唯一識別碼")
    source_contract_id: str = Field(..., description="來源契約 ID")
    change_description: str = Field(..., description="異動描述")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="模型信心值 0~1",
    )
    applied_status: AppliedStatus = Field(
        ...,
        description="實際套用狀態",
    )
    created_at: datetime = Field(..., description="建立時間（UTC）")
    applied_at: Optional[datetime] = Field(
        default=None,
        description="實際套用時間",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="標籤",
    )


class HealthDimension(StrEnum):
    """五維度部門健康度。"""

    VELOCITY = "velocity"
    QUALITY = "quality"
    STABILITY = "stability"
    ALIGNMENT = "alignment"
    CAPACITY = "capacity"


class DimensionScore(BaseModel):
    """單一維度分數與說明。"""

    model_config = {"extra": "ignore"}

    dimension: HealthDimension
    score: float = Field(ge=0.0, le=100.0, description="0~100 分")
    narrative: str = ""
    raw_metrics: Dict[str, float] = Field(default_factory=dict)


class DepartmentHealth(BaseModel):
    """部門健康度摘要。"""

    model_config = {"extra": "ignore"}

    department: str
    dimensions: Dict[HealthDimension, DimensionScore] = Field(default_factory=dict)
    overall_score: float = Field(ge=0.0, le=100.0, default=0.0)
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "command_center_v1"


class DecisionStatus(StrEnum):
    """決策票生命周期。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class DecisionTicket(BaseModel):
    """Founder/Chairman Human Decision Queue 票券。"""

    model_config = {"extra": "ignore"}

    ticket_id: str
    title: str
    description: str = ""
    department: str = ""
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision: Optional[str] = None
