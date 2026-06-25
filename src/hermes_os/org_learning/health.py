"""Organizational Learner — Department Health calculation module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional


class HealthDimension(StrEnum):
    """Five health dimensions for Founder/Chairman view."""

    VELOCITY = "velocity"
    QUALITY = "quality"
    STABILITY = "stability"
    ALIGNMENT = "alignment"
    CAPACITY = "capacity"


@dataclass
class DimensionScore:
    """Single dimension score with narrative."""

    dimension: HealthDimension
    score: float = field(metadata={"ge": 0.0, "le": 100.0})
    narrative: str = ""
    raw_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class DepartmentHealth:
    """Aggregated department health snapshot."""

    department: str
    dimensions: Dict[HealthDimension, DimensionScore] = field(default_factory=dict)
    overall_score: float = 0.0
    computed_at: datetime = field(default_factory=datetime.utcnow)
    source: str = "command_center_v1"


class DepartmentHealthCalculator:
    """Calculate department health from input metrics.

    Default strategy: equal-weight average across the five dimensions.
    Each dimension maps 0-100 based on simple metric heuristics.
    """

    DIMENSION_WEIGHTS = {
        HealthDimension.VELOCITY: 1.0,
        HealthDimension.QUALITY: 1.0,
        HealthDimension.STABILITY: 1.0,
        HealthDimension.ALIGNMENT: 1.0,
        HealthDimension.CAPACITY: 1.0,
    }

    def _score_velocity(self, metrics: Dict[str, float]) -> DimensionScore:
        delivered = float(metrics.get("delivered", 0.0))
        planned = float(metrics.get("planned", 1.0))
        ratio = delivered / planned if planned else 0.0
        score = min(max(ratio * 100.0, 0.0), 100.0)
        narrative = f"已交付 {delivered:.1f} / 計劃 {planned:.1f}"
        return DimensionScore(
            dimension=HealthDimension.VELOCITY,
            score=score,
            narrative=narrative,
            raw_metrics=metrics,
        )

    def _score_quality(self, metrics: Dict[str, float]) -> DimensionScore:
        defect_rate = float(metrics.get("defect_rate", 0.0))
        score = max(100.0 - (defect_rate * 100.0), 0.0)
        narrative = f"缺陷率 {defect_rate:.2%}"
        return DimensionScore(
            dimension=HealthDimension.QUALITY,
            score=score,
            narrative=narrative,
            raw_metrics=metrics,
        )

    def _score_stability(self, metrics: Dict[str, float]) -> DimensionScore:
        incidents = float(metrics.get("incidents", 0.0))
        score = max(100.0 - (incidents * 10.0), 0.0)
        narrative = f"事件數 {incidents:.0f}"
        return DimensionScore(
            dimension=HealthDimension.STABILITY,
            score=score,
            narrative=narrative,
            raw_metrics=metrics,
        )

    def _score_alignment(self, metrics: Dict[str, float]) -> DimensionScore:
        goal_hit = float(metrics.get("goal_hit_rate", 0.0))
        score = min(max(goal_hit * 100.0, 0.0), 100.0)
        narrative = f"目標命中率 {goal_hit:.0%}"
        return DimensionScore(
            dimension=HealthDimension.ALIGNMENT,
            score=score,
            narrative=narrative,
            raw_metrics=metrics,
        )

    def _score_capacity(self, metrics: Dict[str, float]) -> DimensionScore:
        utilization = float(metrics.get("utilization", 0.0))
        # 80-100% 是理想區間；偏低或過高都扣分
        if utilization >= 0.80:
            score = 100.0
        elif utilization >= 0.60:
            score = 80.0
        else:
            score = max(utilization * 100.0, 0.0)
        narrative = f"使用率 {utilization:.0%}"
        return DimensionScore(
            dimension=HealthDimension.CAPACITY,
            score=score,
            narrative=narrative,
            raw_metrics=metrics,
        )

    def compute(
        self,
        department: str,
        metrics: Dict[str, Dict[str, float]],
        *,
        weights: Optional[Dict[HealthDimension, float]] = None,
    ) -> DepartmentHealth:
        """Compute health snapshot for a department.

        metrics keys should be one of the HealthDimension values.
        """
        weights = weights or self.DIMENSION_WEIGHTS
        scorers = {
            HealthDimension.VELOCITY: self._score_velocity,
            HealthDimension.QUALITY: self._score_quality,
            HealthDimension.STABILITY: self._score_stability,
            HealthDimension.ALIGNMENT: self._score_alignment,
            HealthDimension.CAPACITY: self._score_capacity,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        dimensions: Dict[HealthDimension, DimensionScore] = {}
        for dim, scorer in scorers.items():
            dim_metrics = metrics.get(dim.value, {})
            score = scorer(dim_metrics).score
            weight = weights.get(dim, 1.0)
            weighted_sum += score * weight
            total_weight += weight
            dimensions[dim] = scorer(dim_metrics)

        overall = (weighted_sum / total_weight) if total_weight else 0.0
        return DepartmentHealth(
            department=department,
            dimensions=dimensions,
            overall_score=overall,
            source="command_center_v1",
        )


def health_to_signals(health: DepartmentHealth) -> list:
    """Adapter：將 DepartmentHealth 轉為一般化的 signals。"""
    from hermes_os.org_learning.providers import DepartmentHealthSignalProvider

    return DepartmentHealthSignalProvider(
        department=health.department,
        health={
            "department": health.department,
            "overall_score": health.overall_score,
            "computed_at": health.computed_at.isoformat() if hasattr(health.computed_at, "isoformat") else str(health.computed_at),
            "dimensions": {
                k: {"score": v.score, "narrative": v.narrative}
                for k, v in health.dimensions.items()
            },
        },
    ).fetch_signals()
