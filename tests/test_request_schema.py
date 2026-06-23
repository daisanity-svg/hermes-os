"""Request validation tests."""

from __future__ import annotations

import pytest

from hermes_os.request_schema import validate_task_payload, ValidationError


def test_validate_task_payload_success() -> None:
    payload = validate_task_payload({"id": "job-1", "type": "task", "priority": 1})
    assert payload["id"] == "job-1"
    assert payload["priority"] == 1


def test_validate_task_payload_missing_id_raises() -> None:
    with pytest.raises(ValidationError):
        validate_task_payload({"type": "task"})
