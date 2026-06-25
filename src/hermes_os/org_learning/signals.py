"""Organizational Learner — Business Signal schemas for Chairman View."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class SignalCategory(StrEnum):
    """Top-level business signal category."""

    FINANCIAL = "Financial"
    STRATEGIC = "Strategic"
    OPERATIONAL = "Operational"
    RISK = "Risk"


class NumericTrend(StrEnum):
    """Direction of a numeric value compared to the prior period."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class BusinessSignal(BaseModel):
    """Standardized business signal consumed by Command Center."""

    model_config = {"extra": "ignore"}

    signal_id: str = Field(..., description="唯一識別碼")
    category: SignalCategory = Field(..., description="Signal 分類")
    sub_category: str = Field(default="", description="子分類")
    title: str = Field(..., description="Chairman 看到的短標題")
    summary: str = Field(..., description="30 字以內摘要，包含數字與趨勢")
    value: Optional[Union[float, str]] = Field(default=None, description="量化值或文本")
    unit: Optional[str] = Field(default=None, description="單位")
    as_of: datetime = Field(default_factory=datetime.utcnow, description="資料時間")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="信賴度")
    source_system: str = Field(default="", description="來源系統")
    tags: List[str] = Field(default_factory=list, description="標籤")
    related_departments: List[str] = Field(default_factory=list, description="相關部門")
    priority_for_chairman: bool = Field(default=False, description="是否為 Chairman 首要關注")
    numeric_trend: NumericTrend = Field(default=NumericTrend.UNKNOWN, description="趨勢方向")
    is_low_confidence_estimate: bool = Field(default=False, description="是否為低信賴推估值")

    def display_color(self) -> str:
        if self.confidence < 0.5:
            return "grey"
        if self.confidence >= 0.85:
            return "green"
        return "yellow"

    def is_trustworthy(self) -> bool:
        return self.confidence >= 0.85
