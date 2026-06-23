"""Shared validation layer — pydantic schemas for governance records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from hermes_os.types import ActionStatus, RunStatus


class ArtifactRefModel(BaseModel):
    artifact_id: str
    run_id: str
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("filename")
    @classmethod
    def no_path_traversal(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/"):
            raise ValueError("absolute path not allowed")
        if ".." in Path(normalized).parts:
            raise ValueError("path traversal not allowed")
        return Path(normalized).name


class OwnershipRecordModel(BaseModel):
    record_id: str
    subject_id: str
    owner: str
    source: str
    granted_at: Optional[datetime] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class LifecycleEventModel(BaseModel):
    event_id: str
    subject_id: str
    from_status: Optional[str] = None
    to_status: str
    occurred_at: Optional[datetime] = None
    actor: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("to_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {e.value for e in RunStatus}
        if value not in allowed:
            raise ValueError(f"invalid RunStatus: {value}")
        return value


class ActionRecordModel(BaseModel):
    action_id: str
    run_id: Optional[str] = None
    action_type: str
    status: ActionStatus = ActionStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    output_snapshot: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("error")
    @classmethod
    def error_only_with_failure(cls, value: Optional[str], info) -> Optional[str]:
        # pydantic v2 `info` is a ValidationInfo; we just enforce non-empty.
        if value is not None and not value.strip():
            raise ValueError("error must be non-empty when provided")
        return value
