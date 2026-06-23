"""Request validation helpers."""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict, List, Optional


REQUIRED_TASK_FIELDS = ("id", "type")
OPTIONAL_TASK_FIELDS = ("priority", "payload", "parent_id", "group_id")


class ValidationError(Exception):
    pass


def validate_task_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [field for field in REQUIRED_TASK_FIELDS if field not in payload]
    if missing:
        raise ValidationError(f"missing fields: {', '.join(missing)}")
    errors: List[str] = []
    if not isinstance(payload.get("id"), str) or not payload["id"]:
        errors.append("id must be a non-empty string")
    priority = payload.get("priority", 0)
    if not isinstance(priority, int):
        errors.append("priority must be an integer")
    if errors:
        raise ValidationError("; ".join(errors))
    normalized = {
        field: payload[field]
        for field in (*REQUIRED_TASK_FIELDS, *OPTIONAL_TASK_FIELDS)
        if field in payload
    }
    return normalized
